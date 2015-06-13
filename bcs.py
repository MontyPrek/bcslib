from __future__ import division, unicode_literals, print_function, absolute_import
import itertools
import requests

class RequestError(Exception):
    """An error in the http get/post request."""
    def __init__(self, response):
        self.response = response
        message = 'Error {}: {}'.format(response.status_code, response.text)
        super(RequestError, self).__init__(message, self.response)



UCSTATE_START = 18
# big guess
ULSTATE_START = 142

HEADER_LENGTH = 18
UCSTATE_LENGTH = 124
ULSTATE_LENGTH = 32


class Offset(object):
    def __init__(self, data, number):
        # data is read(bcs_proc.cfg).split(',').
        self.data = data
        self.number = number

    def __getitem__(self, idx):
        return self.data[idx+self.number]

    def __setitem__(self, idx, value):
        self.data[idx+self.number] = value


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
            result += HEADER_LENGTH + (UCSTATE_LENGTH * 8) + (ULSTATE_LENGTH * self.state)
        return result

    def get_header(self, idx):
        return self.data[self._head_idx(idx)]

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
    """There are 4 of these per state."""
    def __init__(self, data, number, state):
        assert 0 <= number < 4
        super(Timer, self).__init__(data, number, state)

    def __str__(self):
        return 'Timer {0.name}: enabled={0.enabled}, up_not_down={0.up_not_down}, initial={0.initial}'.format(self)

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


class OutputControl(StateOffset):
    """There are 5 of these per state."""
    def __init__(self, data, number, state):
        assert 0 <= number < 5
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


class ExitCondition(StateOffset):
    def __init__(self, data, number, state):
        assert 0 <= number < 5
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
        assert value is None or 0 <= value < 8, 'Temperature value out of range'
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
    def time_exit(self):
        assert value is None or 0 <= value < 4, 'Timer value out of range'
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



class State(Offset):
    def __init__(self, data, number):
        assert 0 <= number < 8, 'Invalid state number'
        super(State, self).__init__(data, number)
        self.timers = [Timer(data, x, number) for x in range(4)]
        self.output = [OutputControl(data, x, number) for x in range(5)]
        self.exit_conditions = [ExitCondition(data, x, number) for x in range(5)]

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
        # this is probably wrong, have to figure out how to query bcs_proc about states.
        # does it just append their ucstate/ulstate one after the other?
        self.states = [State(data, x) for x in range(8)]

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    @property
    def name(self):
        return self.data[1]

    @name.setter
    def name(self, value):
        self.data[1] = value

    @property
    def state_names(self):
        return self.data[2:10]

    @state_names.setter
    def state_names(self, values):
        for idx, value in enumerate(values, start=2):
            self.data[idx] = value

    @property
    def timer_names(self):
        return self.data[10:14]

    @timer_names.setter
    def timer_names(self, values):
        for idx, value in enumerate(values, start=10):
            self.data[idx] = value

    @property
    def web_input_names(self):
        return self.data[14:18]

    @web_input_names.setter
    def web_input_names(self, values):
        for idx, value in enumerate(values, start=14):
            self.data[idx] = value


class Client(object):
    """A client. Just to store that stupid address parameter.

    :param ivar address: The address of the client.
    """
    def __init__(self, address):
        self.address = address

    def get(self, filename, params=None):
        """Get the "Open interface file" specified as a csv string.

        :param str filename: The filename to get
        :param str params: The parameters string to use '(?p=x&s=y' to get process x state y, maybe).
        """
        url = '{}/{}'.format(self.address, filename)
        result = requests.get(url, params=params)
        if not result.ok:
            raise RequestError(result)
        return result.text

    def put_bcs(self, filename, data, params):
        """Post the "Open interface file" specified"""
        url = '{}/{}'.format(self.address, filename)
        result = requests.post(url, data=data, params=params)
        if not result.ok:
            raise RequestError(result)
        return result.text

    def get_process_name(self, process_num):
        """Get the name information about a process.
        First query the relevant names and pull them out of sysname.dat.
        Then query the ulstate/ucstate.dat files.
        """
        assert 0 <= process_num < 8, 'invalid process number'
        data = get_bcs('bcs_proc.cfg', params='?p={}&'.format(process_num)).split(',')
        fields = data.split(',')
        return {
            'process_name': fields[1],
            'state_names': fields[2:10],
            'timer_names': fields[10:14],
            'web_input_names': fields[14:18]
        }

    def get_state_info(self, process_num, state_num):
        """Each process has 8 states.

        TODO: Instead of just lists, build thesem into some more useful representation.
        """
        # TODO: Figure out which temperature/output sensors are used and stub out the fields
        # with a marker. Then do the reverse on set_state_info
        params = 'p={}&s={}'.format(process_num, state_num)
        return {
            'ulstate': self.get_bcs('ulstate.dat', params).split(','),
            'ucstate': self.get_bcs('ucstate.dat', params).split(',')
        }


    def get_process(self, process_num):
        """Return a process as a dictionary.

        TODO: Figure out how bcs_proc.cfg is laid out. Is it just appended?
        It might be easier to use that than to use the individual docs. But
        first we have to figure out if they're just concatenated or if they
        have separators, etc. Check w/ actual BCS unit.

        TODO: The way bcs_proc.cfg is laid out
            - the defined header stuff
            - ucstate.dat for state 0
            - ucstate.dat for state ...
            - ulstate.dat for state 0
            - ulstate.dat for state ...
        """
        return {
            'names': self.get_process_name(process_num),
            'states': [self.get_state_info(process_num, state_num)
                       for state_num in range(8)]
        }

    def set_process_name(self, process_num, process):
        """Set the name information about a process.
        First query the existing information, then replace that with new information.
        """
        data = self.get_bcs('bcs_proc.cfg')
        fields = data.split(',')
        fields[1] = process['process_name']
        fields = itertools.chain(
            enumerate(process['state_names'], start=2),
            enumerate(process['timer_names'], start=10),
            enumerate(process['web_input_names'], start=14)
        )
        newdata = ','.join(fields)
        # PUT the new list. the params field is required.
        # TODO: TEST: It may be required as a parameter instead of data? Docs are unclear.
        # can't use dict form of params because order matters (wtf) and you can't get ?data& that way.
        self.put_bcs('sysname.dat', newdata, params='data&p=0&s=0')


    def set_state_info(self, process_num, state_num, state_data):
        """Set the state info."""
        params = 'p={}&s={}'.format(process_num, state_num)
        self.put_bcs('ulstate.dat', ','.join(state_data['ulstate']), params)
        self.put_bcs('ucstate.dat', ','.join(state_data['ucstate']), params)

    def set_process(self, process_num, process_data):
        """Set a process based on the given data.

        TODO: Same considerations as get_process
        """
        self.set_process_name(process_num, process_data['names'])
        for state_num, state_data in enumerate(process_num['states']):
            self.set_state_info(process_num, state_num, state_data)

    def get_process_to_file(self, process_num, path):
        process_data = self.get_process(process_num)
        with open(path, 'w') as fp:
            json.dump(process_data, fp)

    def set_process_from_file(self, process_num, path):
        with open(path, 'r') as fp:
            process_data = json.load(fp)
        self.set_process(process_num, process_data)


