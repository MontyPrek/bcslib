from __future__ import division, unicode_literals, print_function, absolute_import
import itertools
import requests

class RequestError(Exception):
    """An error in the http get/post request."""
    def __init__(self, response):
        self.response = response
        message = 'Error {}: {}'.format(response.status_code, response.text)
        super(RequestError, self).__init__(message, self.response)



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
            'ulstate': self.get_bcs('ulstate.dat', params).split(',')
            'ucstate': self.get_bcs('ucstate.dat', params).split(',')
        }


    def get_process(self, process_num):
        """Return a process as a dictionary.

        TODO: Figure out how bcs_proc.cfg is laid out. Is it just appended?
        It might be easier to use that than to use the individual docs. But
        first we have to figure out if they're just concatenated or if they
        have separators, etc. Check w/ actual BCS unit.
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


