from __future__ import (division, unicode_literals, print_function,
                        absolute_import)
import json
from urllib.parse import urlparse
import requests


class RequestError(Exception):
    """An error in the http get/post request."""
    def __init__(self, response):
        self.response = response
        message = 'Error {}: {}'.format(response.status_code, response.text)
        super(RequestError, self).__init__(message, self.response)


class IllegalRequestError(Exception):
    """A request with illegal parameters was attempted"""
    def __init__(self, attempt):
        self.attempt = attempt
        message = 'Error: {} cannot be {}'.format(attempt['name'],
                                                  attempt['val'])
        super(IllegalRequestError, self).__init__(message, self.attempt)


HEADER_LENGTH = 18
UCSTATE_LENGTH = 124
ULSTATE_LENGTH = 32


class StateOffset(object):
    def __init__(self, data, number, state):
        assert 0 <= state < 8
        self.data = data
        self.number = number
        self.state = state

    def _head_idx(self, idx, ucstate=False, ulstate=False):
        assert not (ucstate and ulstate)
        result = idx + self.number
        if ucstate:
            result += HEADER_LENGTH + (UCSTATE_LENGTH * self.state)
        elif ulstate:
            result += (HEADER_LENGTH + (UCSTATE_LENGTH * 8) +
                       (ULSTATE_LENGTH * self.state))
        return result

    def get_header(self, idx):
        return self.data[self._head_idx(idx)].rstrip()

    def set_header(self, idx, value):
        self.data[self._head_idx(idx)] = value

    def get_ucstate(self, idx):
        return self.data[self._head_idx(idx, ucstate=True)]

    def set_ucstate(self, idx, value):
        self.data[self._head_idx(idx, ucstate=True)] = value

    def get_ulstate(self, idx):
        return self.data[self._head_idx(idx, ulstate=True)]

    def set_ulstate(self, idx, value):
        self.data[self._head_idx(idx, ulstate=True)] = value


class Timer(StateOffset):
    """There are 4 of these per process, shared across the states. Each state
    has individual
    settings for each timer (whether to enable it, etc.)
    """
    def __init__(self, data, number, state):
        assert 0 <= number < 4
        super(Timer, self).__init__(data, number, state)

    def __str__(self):
        return ('Timer {0.name}: enabled={0.enabled}, '
                'up_not_down={0.up_not_down},initial={0.initial}'
                ).format(self)

    @property
    def name(self):
        return self.get_header(10)

    @name.setter
    def name(self, value):
        self.set_header(10, value)

    @property
    def enabled(self):
        return self.get_ucstate(18)

    @enabled.setter
    def enabled(self, value):
        self.set_ucstate(18, value)

    @property
    def up_not_down(self):
        return self.get_ucstate(22)

    @up_not_down.setter
    def up_not_down(self, value):
        self.set_ucstate(22, value)

    @property
    def initial(self):
        return self.get_ulstate(0)

    @initial.setter
    def initial(self, value):
        self.set_ulstate(0, value)


# TODO:
# Needs __str__
class OutputControl(StateOffset):
    """There are 6 of these per state."""
    def __init__(self, data, number, state):
        assert 0 <= number < 6
        super(OutputControl, self).__init__(data, number, state)

    @property
    def control_type(self):
        return self.get_ucstate(0)

    @control_type.setter
    def control_type(self, value):
        self.set_ucstate(0, value)

    @property
    def control_value(self):
        return self.get_ucstate(26)

    @control_value.setter
    def control_value(self, value):
        self.set_ucstate(26, value)

    @property
    def temp_setpoint(self):
        return self.get_ulstate(4)

    @temp_setpoint.setter
    def temp_setpoint(self, value):
        self.set_ulstate(4, value)


# TODO:
# Needs __str__
class ExitCondition(StateOffset):
    def __init__(self, data, number, state):
        assert 0 <= number < 4
        super(ExitCondition, self).__init__(data, number, state)

    @property
    def temp_exit(self):
        for count, idx in enumerate(range(32, 36)):
            found = int(self.get_ucstate(idx))
            if found == 0:
                continue
            elif found == 1:
                return count
            elif found == 2:
                return count + 4
            else:
                raise ValueError('Got {}, expected (0, 1, 2)'.format(found))

    @temp_exit.setter
    def temp_exit(self, value):
        assert value is None or 0 <= value < 8,\
            'Temperature value out of range'
        for count, idx in enumerate(range(32, 36)):
            if value is not None and (value % 4) == count:
                self.set_ucstate(idx, str(value//4 + 1))
            else:
                self.set_ucstate(idx, '0')

    @property
    def time_exit(self):
        for count, idx in enumerate(range(48, 52)):
            found = int(self.get_ucstate(idx))
            if found == 0:
                continue
            elif found == 1:
                return count
            else:
                raise ValueError('Got {}, expected (1, 2)'.format(found))

    @time_exit.setter
    def time_exit(self, value):
        assert value is None or 0 <= value < 4, 'Timer value out of ran218ge'
        for count, idx in enumerate(range(48, 52)):
            if value is not None and value == count:
                self.set_ucstate(idx, '1')
            else:
                self.set_ucstate(idx, '0')

    @property
    def discrete_input_exit(self):
        for count, idx in enumerate(range(64, 68)):
            found = int(self.get_ucstate(idx))
            if found == 0:
                continue
            elif found == 1:
                return count
            elif found == 6:
                return count + 4
            else:
                raise ValueError('Got {}, expected (0, 1, 6)'.format(found))

    @discrete_input_exit.setter
    def discrete_input_exit(self, value):
        assert value is None or 0 <= value < 8, 'Discrete input out of range'
        for count, idx in enumerate(range(64, 68)):
            if value is not None and (value % 4) == count:
                self.set_ucstate(idx, str(5 * (value//4)))
            else:
                self.set_ucstate(idx, '0')

    @property
    def web_input_exit(self):
        for count, idx in enumerate(range(80, 84)):
            found = int(self.get_ucstate(idx))
            if found == 0:
                continue
            elif found == 1:
                return count
            else:
                raise ValueError('Got {}, expected (1, 2)'.format(found))

    @web_input_exit.setter
    def web_input_exit(self, value):
        assert value is None or 0 <= value < 4, 'Web input out of range'
        for count, idx in enumerate(range(80, 84)):
            if value is not None and value == count:
                self.set_ucstate(idx, '1')
            else:
                self.set_ucstate(idx, '0')

    @property
    def next_state(self):
        return self.get_ucstate(96)

    @next_state.setter
    def next_state(self, value):
        self.set_ucstate(96, value)

    @property
    def test_value(self):
        return self.get_ucstate(100)

    @test_value.setter
    def test_value(self, value):
        self.set_ucstate(100, value)

    @property
    def value_is_greater_than(self):
        return self.get_ucstate(108)

    @value_is_greater_than.setter
    def value_is_greater_than(self, value):
        self.set_ucstate(108, value)

    @property
    def temperature(self):
        return self.get_ulstate(10)

    @temperature.setter
    def temperature(self, value):
        self.set_ulstate(10, value)

    @property
    def time(self):
        return self.get_ulstate(14)

    @time.setter
    def time(self, value):
        self.set_ulstate(14, value)


class State(StateOffset):
    def __init__(self, data, state):
        assert 0 <= state < 8, 'Invalid state number'
        super(State, self).__init__(data, state, state)
        self.timers = [Timer(data, x, state) for x in range(4)]
        self.output = [OutputControl(data, x, state) for x in range(6)]
        self.exit_conditions = [ExitCondition(data, x, state)
                                for x in range(4)]

    def __str__(self):
        return ('State {0.name}:\n\ttimers={0.timers}\n\toutput={0.output}'
                '\n\texit_conditions={0.exit_conditions}').format(self)

    @property
    def name(self):
        return self.get_header(2)

    @name.setter
    def name(self, value):
        self.set_header(2, value)


class Process(object):
    def __init__(self, data):
        self.data = data
        self.states = [State(data, x) for x in range(8)]

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    @property
    def name(self):
        return self.data[1].rstrip()

    @name.setter
    def name(self, value):
        self.data[1] = value

    @property
    def state_names(self):
        return [x.strip() for x in self.data[2:10]]

    @state_names.setter
    def state_names(self, values):
        for idx, value in enumerate(values, start=2):
            self.data[idx] = value

    @property
    def timer_names(self):
        return [x.strip() for x in self.data[10:14]]

    @timer_names.setter
    def timer_names(self, values):
        for idx, value in enumerate(values, start=10):
            self.data[idx] = value

    @property
    def web_input_names(self):
        return [x.strip() for x in self.data[14:18]]

    @web_input_names.setter
    def web_input_names(self, values):
        for idx, value in enumerate(values, start=14):
            self.data[idx] = value


class Client(object):
    """A client. Just to store that stupid address parameter.

    :param ivar address: The address of the client.
    """
    def __init__(self, address, username, password):
        parsed = urlparse(address)
        if not parsed.netloc:
            address = 'http://{}'.format(address)
        self.address = address
        self.auth = (username, password)

    def get_bcs(self, filename, params=None):
        """Get the "Open interface file" specified as a csv string.

        :param str filename: The filename to get
        :param str params: The parameters string to use
            ('?p=x&s=y' to get process x state y, maybe).
        """
        url = '{}/{}'.format(self.address, filename)
        result = requests.get(url, params=params, auth=self.auth)
        if not result.ok:
            raise RequestError(result)
        return result.text

    def post_bcs(self, filename, data, params):
        """Post the "Open interface file" specified"""
        url = '{}/{}'.format(self.address, filename)
        result = requests.post(url, data=data, params=params, auth=self.auth)
        if not result.ok:
            raise RequestError(result)
        return result.text

    def get_process(self, process_num):
        """Return a process object for the requested process number.

        :param process_num: The number of the requested process
        :type process_num: int

        :return: A populated process object
        :rtype: Process
        """
        if not 0 <= process_num < 8:
            raise IllegalRequestError({'name': 'Process number',
                                       'val': process_num})

        data = self.get_bcs('bcs_proc.cfg',
                            params='?p={}&'.format(process_num))
        fields = data.split(',')
        return Process(fields)

    def set_process(self, process_num, process):
        """Post the given process to the BCS under the given process number.

        :param process_num: The number to post the process to
        :type process_num: int
        :param process: The process to post
        :type process: Process
        """

        if not 0 <= process_num < 8:
            raise IllegalRequestError({'name': 'Process number',
                                       'val': process_num})
        self.post_bcs('bcs_proc.cfg', data=process.data,
                      params='?data&p={0}&s={0}&'.format(process_num))

    def get_process_to_file(self, process_num, path):
        process_data = self.get_process(process_num).data
        with open(path, 'w') as fp:
            json.dump(process_data, fp)

    def set_process_from_file(self, process_num, path):
        with open(path, 'r') as fp:
            process_data = json.load(fp)
        self.set_process(process_num, Process(process_data))
