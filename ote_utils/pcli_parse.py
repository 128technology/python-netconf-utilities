import re

'''
***Not To Be Released to Thrid Party***
Module that holds pure pcli parsing methods
These methods take pcli output and return a
formated dictornary
'''

def parse_show_version(output, execution_time):
    """Parses 128T version info into standard dict

    Args:
        output (str): Scraped pcli command dump
        execution_time (float): time taken to colect `output`

    Returns:
        dict: formated dict containing elements of command output
    """
    show_list = []
    output, dictionary = _prep_show_output(output, execution_time)

    for data_line in output.splitlines():
        fields = data_line.split(':', 1)
        value = fields[1].lstrip()
        cur_dictionary = {fields[0]: value}
        show_list.append(cur_dictionary)

    dictionary.update({'show': show_list})
    return dictionary

def parse_show_command(output, execution_time):
    """ Parses generic show command
    *I95-11259, doesn't include all support

    Args:
        output (str): Scraped pcli command dump
        execution_time (float): time taken to colect `output`

    Returns:
        dict: formated dict containing elements of command output
    """
    output, dictionary = _prep_show_output(output, execution_time)
    table_title, output = _strip_table_title(output)
    tables_list = _get_tables_list(output)
    show_list = _parse_show_into_dictionary(tables_list)
    dictionary.update({'show': show_list})
    dictionary.update(table_title)
    return dictionary

def _get_tables_list(output):
   tables_list = []
   positions = []
   for count, item in enumerate(output.split("\n")):
       if '==' in item:
           positions.append(count)

   positions = positions[2::2]
   start_position = 0
   if positions:
       for position in positions:
           if position == positions[-1]:
               table = '\n'.join(output.split('\n')[start_position:position - 1])
               tables_list.append(table)
               start_position = position - 1
               table = '\n'.join(output.split('\n')[start_position:])
           else:
               table = '\n'.join(output.split('\n')[start_position:position - 1])
               start_position = position - 1
           tables_list.append(table)
   else:
       tables_list = [output]

   return tables_list

def _clean_show_ouput(output):
    output = _strip_empty_lines(output)
    output = _strip_line_containing_match(output, 'Retrieving')
    return output

def _prep_show_output(cli_output, execution_time):
    dictionary = {}
    execution_time = {'execution_time': '{:.2f} seconds'.format(execution_time)}
    output = _clean_show_ouput(cli_output)
    timestamp, output = _strip_timestamp(output)
    completion_time, output = _strip_completion_time(output)
    dictionary.update(timestamp)
    dictionary.update(completion_time)
    dictionary.update(execution_time)
    return output, dictionary

def _parse_show(values, columns, headers, node, table_separator_length):
   list_of_dict = []
   for output in values.splitlines():
       values = _parse_columns(output, columns, table_separator_length)
       if len(node):
           head = list(headers)
           values.insert(0, node)
           head.insert(0, 'Node')
       else:
           head = list(headers)
       data_dict = dict(zip(head, values))
       list_of_dict.append(data_dict)

   return list_of_dict

def _parse_show_into_dictionary(tables_list):
    show_dictionary_list = []
    for table in tables_list:
        delimiter_line = _get_delimiter_line(table)
        if delimiter_line is None:
            break
        columns = delimiter_line.split()
        spaces = re.findall('\s+', delimiter_line)
        if len(spaces) == 0:
            table_separator_length = 0
        else:
            table_separator_length = len(spaces[0])
        values, headers, node = _divide_output(table, columns, table_separator_length)
        show_list = _parse_show(values, columns, headers, node, table_separator_length)
        show_dictionary_list.append(show_list)

    show_dictionary_list = _flatten_show(show_dictionary_list)
    return show_dictionary_list

def _parse_columns(output, columns, table_separator_length):
    headers = []
    start = 0
    for column in columns:
        end = len(column) + start
        item = output[start:end]
        start = end + table_separator_length
        item = item.lstrip()
        item = item.rstrip()
        headers.append(item)
    return headers

def _parse_keyword_arguments(output):
    keyword_arguments = []
    output = _strip_leading_space_lines(output)
    positional_index = _get_line_index_from_string(output, 'positional arguments')
    line_index = _get_line_index_from_string(output, 'keyword arguments')
    if line_index:
        output = output.splitlines()[0:positional_index - 2]
        del output[0:line_index]
        for help_string in output:
            keyword_argument = help_string.partition(' ')[0]
            keyword_arguments.append(keyword_argument)
    return keyword_arguments

def _parse_subcommand(output, command):
    subcommands = []
    for help_string in output:
        subcommand = help_string.partition(' ')[0]
        subcommands.append(str(command) + ' ' + subcommand)
    return subcommands

def _get_delimiter_line(output):
    for item in output.split("\n"):
        if '==' in item:
            return item

def _get_line_index_from_string(output, string):
    line_number = False
    for num, line in enumerate(output.splitlines(), 1):
        if string in line:
            line_number = num
    return line_number

def _divide_output(output, columns, table_separator_length):
    output = _strip_line_containing_match(output, '==')
    pattern = re.compile('Node name:')
    if pattern.match(output.splitlines()[0]):
        headers = _parse_columns(output.splitlines()[1], columns, table_separator_length)
        node = output.split('\n')[0]
        node = node.split('Node name:', 1)[1]
        node = node.strip()
        values = '\n'.join(output.split("\n")[2:])
    else:
        headers = _parse_columns(output.splitlines()[0], columns, table_separator_length)
        node = ''
        values = '\n'.join(output.split('\n')[1:])
    return values, headers, node

def _flatten_show(show_list):
    return [item for show in show_list for item in show]

def _strip_timestamp(output):
    timestamp = output.splitlines()[0]
    timestamp = {'timestamp': timestamp}
    output = '\n'.join(output.split('\n')[1:])
    return timestamp, output

def _strip_prompt(output):
    output = '\n'.join(output.split('\n')[0:-1])
    return output

def _strip_completion_time(output):
    completion_time = output.splitlines()[-1]
    completion_time = completion_time.split('Completed in ')[1]
    completion_time = {'completion_time': completion_time}
    output = '\n'.join(output.split('\n')[0:-1])
    return completion_time, output

def _strip_table_title(output):
    line_index = [output.splitlines().index(delimiter)
                  for delimiter in output.splitlines() if '---' in delimiter]
    if line_index:
        table_title = output.splitlines()[line_index[0] - 1]
        table_title = {'table_title': table_title}
        output = output.splitlines()
        output.pop(line_index[0])
        output.pop(line_index[0] - 1)
        output = '\n'.join(output)
    else:
        table_title = {'table_title': None}
    return table_title, output

def _strip_empty_lines(output):
    return '\n'.join([x for x in output.split("\n") if x.strip() != ''])

def _strip_leading_space_lines(output):
    return '\n'.join([x for x in output.split("\n") if x.startswith(" ") is not True])

def _strip_line_containing_match(output, match_string):
    return '\n'.join([x for x in output.split("\n") if match_string not in x])
