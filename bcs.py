

def get_bcs(address, filename, params=None):
    """Get the "Open interface file" specified"""
    url = '{}/{}'.format(address, filename)
    result = requests.get(url, params=params)
    if not result.ok:
        raise RequestError(result)
    return result.text


def put_bcs(address, filename, data, params):
    """Post the "Open interface file" specified"""
    url = '{}/{}'.format(address, filename)
    result = requests.post(url, data=data, params=params)
    if not result.ok:
        raise RequestError(result)
    return result.text


def _name_fields(process_num):
    if process_num < 4:
        procname_idx = 1 + process_num
        state_start = 5 + (process_num * 8)
        win_start = 47 + (process_num * 4)
        timer_start = 67 + (process_num * 4)
    elif process_num < 8:
        procname_idx = 105 + (process_num - 4)
        state_start = 109 + ((process_num - 4) * 8)
        win_start = 141 + ((process_num - 4) * 4)
        timer_start = 157 + ((process_num - 4) * 4)
    else:
        raise ValueError('Process number must be <8 and > 0')
    return procname_idx, state_start, win_start, timer_start


def get_process_name(address, process_num):
    """Get the name information about a process.
    First query the relevant names and pull them out of sysname.dat.
    Then query the ulstate/ucstate.dat files.
    """
    data = get_bcs(address, 'sysname.dat')
    fields = data.split(',')
    procname_idx, state_start, win_start, timer_start = _name_fields(process_num)
    return {
        'process_name': fields[procname_idx],
        'state_names': [x for x in fields[state_start:state_start+8]]
        'web_input_names': [x for x in fields[win_start:win_start+4]]
        'timer_names': [x for x in fields[timer_start:timer_start+4]]
    }


def set_process_name(address, process_num, process):
    """Set the name information about a process.
    First query the existing information, then replace that with new information.
    """
    data = get_bcs(address, 'sysname.dat')
    existing = data.split(',')
    procname_idx, state_start, win_start, timer_start = _name_fields(process_num)
    existing[procname_idx] = process['process_name']
    for idx, value in zip(range(state_start, state_start+8), process['state_names']):
        existing[idx] = value
    for idx, value in zip(range(win_start, win_start+4), process['web_input_names']):
        existing[idx] = value
    for idx, value in zip(range(timer_start, timer_start+4), process['timer_names']):
        existing[idx] = value
    # can't use dict form of params because order matters (wtf) and you can't get ?data& that way.
    put_bcs(address, 'sysname.dat', ','.join(existing), params='data&p=0&s=0')



def get_state_info(address, process_num, state_num):
    """Each process has 8 states."""
    # TODO: Figure out which temperature/output sensors are used and stub out the fields
    # with a marker. Then do the reverse on set_state_info
    params = 'p={}&s={}'.format(process_num, state_num)
    return {
        'ulstate': get_bcs(address, 'ulstate.dat', params).split(',')
        'ucstate': get_bcs(address, 'ucstate.dat', params).split(',')
    }


def set_state_info(address, process_num, state_num, state_data):
    params = 'p={}&s={}'.format(process_num, state_num)
    put_bcs(address, 'ulstate.dat', ','.join(state_data['ulstate']), params)
    put_bcs(address, 'ucstate.dat', ','.join(state_data['ucstate']), params)


def get_process(address, process_num):
    """Return a process as a dictionary."""
    return {
        'names': get_process_name(address, process_num),
        'states': [get_state_info(address, process_num, state_num)
                   for state_num in range(8)]
    }



def set_process(address, process_num, process_data):
    """Set a process based on the given data."""
    set_process_name(address, process_num, process_data['names'])
    for state_num, state_data in enumerate(process_num['states']):
        set_state_info(address, process_num, state_num, state_data)


def get_process_to_file(address, process_num, path):
    process_data = get_process(address, process_num)
    with open(path, 'w') as fp:
        json.dump(process_data, fp)


def set_process_from_file(address, process_num, path):
    with open(path, 'r') as fp:
        process_data = json.load(fp)
    set_process(address, process_num, process_data)


