from abc import ABC, abstractmethod
import ipaddress
import json
import pathlib
import re
import time

from ote_utils.ote_logger import OteLogger

logger = OteLogger(__name__)


class ConfigGenerator:
    """
        This class can generate unique copies of templates, defined by variables that the user
        passes in.

        A user must provide a template, template variables, and the number of copies to create.

        A template is a list of strings that contain the config (or whatever should be duplicated).
        this template will be iterated over for every combination of variables. They can be passed
        directly, or read from a directory - each .txt and .j2 file in that directory will be used.

        the template variables will find a certain substring within each string in your template,
        and substitute their values for each iteration. They can be passed directly, or read from a
        JSON file. the dictionaries/JSON used to create these variables need certain parameters:

            name (str) : the key used to access a variable's parameters is the name of that
                         variable. the following parameters are defined for each key to the
                         outer dictionary.

            type (str) : type of variable being created. Should be one of the values in the
                         VariableFactory map.
            depends_on (str) : name of another variable, or None. Only one variable can have None,
                              and no two variables can depend on the same variable.
            num_iters (int) : number of times this variable iterates per a parent iteration (.e.g
                              "Node" may iterate twice over "Router" - router1a, router1b,
                              router2a, ...)
            target (str) : the string that this variable will replace in your templates (for
                           example, node might replace "{{ Node }}" in a jinja template)
            start (varies): the first iteration of this variable. Should match the variable type.
            step  (varies): the step by which this variable iterates.
                            strings can go by "alphabet" (e.g. abc -> abd) or by appending the step
                            ("a" = abc -> abca, abcaa)).
                            numbers and IPs iterate by the value here.
                            list indices will increase by this number.
            resets (str) : when this variable finishes its num_iters for its parent, should it
                           return to the start value or continue where it left off? ("yes" or "no")
            filename (str) : only needed for a list type. this reads in the list of values from a
                             text file. values are separated by newlines.
    """

    def __init__(self):
        self.template = ConfigGenerator.ConfigTemplate()
        self.var_generator = ConfigGenerator.VariableGenerator()
        self.all_template_iterations = []
        self.prefix = []
        self.suffix = []

    def add_templates(self, templates):
        """
            Adds a template provided by the user to the ConfigGenerator. If it receives a single
            template (a flat list), it will be used as is, but if it receives multiple (a list of
            flat lists), it will attempt to combine them into a single list.

            Args:
                one, but not both, of the following arguments has to be specified.

                templates (list): either a list of only strings, or a list of lists that contain 
                                  only strings.

            Example:
                flat_template = ["line1", "line2", "line3"]
                ConfigGenerator.add_templates(flat_template)
                # Internally, ConfigGenerator now has
                # ["line1", "line2", "line3"]


                my_templates = [
                    ["file1_line1", "file1_line2", "file1_line3"],
                    ["file2_line1", "file2_line2", "file2_line3"]
                ]
                ConfigGenerator.add_templates(my_templates)

                # internally, ConfigGenerator now has [
                # "file1_line1", "file1_line2", "file1_line3",
                # "file2_line1", "file2_line2", "file2_line3"
                # ]

        """
        for item in templates:
            if type(item) == type([]):
                self.template._add_templates(templates)
                return
        self.template._add_template(templates)

    def add_templates_from_directory(self, template_dir):
        """
            Adds Templates to the config generator, by reading .txt or .j2 files from a
            directory.

            Args:
                template_dir (str): path to a directory. the class will read all .txt and .j2 files
                                    in that directory and use the combination of all of them as the
                                    template. 
        """
        self.template._add_templates_from_directory(template_dir)

    def add_vars(self, vars):
        """
            Adds variables to the config generator, by accepting a list of dicts from the user.

            Args:
                vars (dict of dicts): contains a dictionary for each variable that will be
                                      substituted into the template. see class docstring
                                      for what these dicts should contain.
        """
        logger.debug(f"adding config_gen variables: {vars}")
        self.var_generator._add_vars(vars)

    def add_vars_from_file(self, path_to_vars_json):
        """
            Adds variables to the config generator, by reading a json file.

            Args:
                path_to_vars_json (str): a string containing the relative path to + the filename of
                                         a json file.
        """
        logger.debug(f"reading config_gen variables from file: {path_to_vars_json}")
        self.var_generator._add_vars_from_file(path_to_vars_json)

    def add_config_prefix(self, prefix):
        """
            Prepends the list of strings to the generated config.

            Args:
                prefix (list of strings): strings that are added to the generated output
        """
        self.prefix = prefix

    def add_config_suffix(self, suffix):
        """
            Appends the list of strings to the generated config. 

            Args:
                suffix (list of strings): strings that are added to the generated output
        """
        self.suffix = suffix

    def set_copy_count(self, copies):
        """
            Sets the number of times to substitute all variable permutations into the template

            Args:
                copies (int): the number of times to substitute all variable permutations into the
                              template
        """
        self.var_generator._set_quantity(copies)

    def clear_templates(self):
        """
            Removes the current template from the utility.

            Args:
                None
        """
        self.template._clear_templates()

    def clear_vars(self):
        """
            Removes the current variables from the utility.

            Args:
                None
        """
        self.var_generator._clear_vars()

    def clear_config_prefix(self):
        """
            Removes the current prefix from the utility.

            Args:
                None
        """
        self.prefix = []

    def clear_config_suffix(self):
        """
            Removes the current suffix from the template.

            Args:
                None
        """
        self.suffix = []

    def get_generated_config(self, flat=True):
        """
            Returns all of the config that has been generated, or [] if none has been generated.

            Args:
                flat (bool): if True, return a flat list of all iterations.

            Returns:
                list of list of strings if flat=False, a list of strings if flat=True, or [] if
                no config has been generated.

                flat=False ==> [["template", "iteration1"],["template", "iteration2"], ...]
                flat=True ==>  ["template", "iteration1", "template", "iteration2", ...]
        """
        if flat:
            output = []
            for iter in self.all_template_iterations:
                output += iter
            return output
        return self.all_template_iterations

    def write_generated_config_to_file(self, path_to_file, overwrite=False):
        """
            Writes generated config to an output file (one line per string).

            Args:
                path_to_file (str): relative or full path to a file to which output should
                                    be written.
                overwrite (bool): if True, clears the output file before writing to it

            Returns:
                None, but creates/appends to that output file.
        """
        logger.debug(f"writing generated config to {path_to_file}")
        path_to_file = pathlib.Path(path_to_file)
        if overwrite:
            logger.debug(f"wiping {path_to_file} before writing")
            open(path_to_file, "w").close()
        of = open(path_to_file, "a")
        for iteration in self.all_template_iterations:
            of.writelines(iteration)
        of.close()

    def generate_config(self):
        """
            Will attempt to generate config from the variables, copy count, and template.

            Args:
                None, but the variables, count, and template must be manually set, or this
                function won't generate anything.

            Returns:
                None, but the generated config can be retrieved via get_generated_config()
                or write_generated_config_to_file().
        """
        logger.debug(
            f"generating config with {self.var_generator.quantity} copies, "
            f"{len(self.var_generator.vars)} variables, "
            f"and a {len(self.template.template)}-line template"
        )
        self.all_template_iterations = []
        if len(self.prefix):
            self.all_template_iterations.append([] + self.prefix)
        variables = self.var_generator._generate_variable_combinations()
        for variable_iter in variables:
            template_iter = self.template._generate_with_variables(variable_iter)
            self.all_template_iterations.append(template_iter)
        if len(self.suffix):
            self.all_template_iterations.append([] + self.suffix)

    class ConfigTemplate:
        """
            Used by the ConfigGenerator class to populate the templates with different variable
            combinations.
        """

        def __init__(self):
            self.template = []

        def _add_template(self, template):
            self.template = template

        def _add_templates(self, templates):
            self.template = self._combine_templates(templates)

        def _add_templates_from_directory(self, template_directory):
            self.template = self._open_and_combine_templates(template_directory)

        def _clear_templates(self):
            self.template = []

        def _generate_with_variables(self, vars):
            generated_lines = []
            for line in self.template:
                generated_line = line
                for var in vars:
                    generated_line = generated_line.replace(var["target"], var["value"])
                generated_lines.append(generated_line)
            return self._remove_empty_lines(generated_lines)

        def _combine_templates(self, templates):
            full_template = []
            for template in templates:
                full_template += template
            return full_template

        def _open_and_combine_templates(self, path_to_templates):
            templates = []
            current_dir = pathlib.Path(path_to_templates)
            for file in current_dir.iterdir():
                if str(file).endswith(".txt") or str(file).endswith(".j2"):
                    templates.append(open(file, "r").readlines())
            return self._combine_templates(templates)

        def _remove_empty_lines(self, mylist):
            newlist = []
            for line in mylist:
                if line.strip() == "":
                    continue
                newlist.append(line)
            return newlist

    class VariableGenerator:
        """
            The VariableGenerator class is used by the ConfigGenerator class to create all of the
            different variable combinations with the given variable parameters.
        """

        def __init__(self):
            self.var_factory = ConfigGenerator.VariableFactory()
            self.vars = []
            self.quantity = 0

        def _set_quantity(self, quantity):
            self.quantity = quantity

        def _add_vars(self, var_dicts):
            self.vars = self._assemble_node_structure(var_dicts)

        def _add_vars_from_file(self, path_to_vars_json):
            var_dicts = json.load(open(pathlib.Path(path_to_vars_json), "r"))
            self.vars = self._assemble_node_structure(var_dicts, path_to_vars_json)

        def _clear_vars(self):
            self.vars = []

        def _generate_variable_combinations(self):
            permutations = self._calculate_num_permutations()
            var_lists = self._generate_variable_lists(permutations)
            list_size = permutations * self.quantity
            logger.debug(f"generating {list_size} permutations")
            for iter in range(list_size):
                combo = [var_lists[var][iter] for var in range(len(var_lists))]
                yield combo

        def _calculate_num_permutations(self):
            permutations = 1
            for node in range(len(self.vars)):
                permutations *= self.vars[node].num_iters
                self.vars[node]._set_total_iters(permutations)
            return permutations

        def _generate_variable_lists(self, permutations):
            var_lists = []
            total_size = permutations * self.quantity
            for node in range(len(self.vars)):
                list_size = self.quantity * self.vars[node].total_iters
                var_lists.append(
                    self.vars[node]._get_variable_list(list_size)
                    * int(total_size / max(list_size, 1))
                )
            return var_lists

        def _assemble_node_structure(self, var_dicts, template_directory="./"):
            vars = self._create_node_objects(var_dicts, template_directory)
            head = self._create_node_assocations(vars)
            return self._verify_and_sort_node_structure(head, vars)

        def _create_node_objects(self, var_dicts, template_dir):
            vars = []
            for var_name in var_dicts.keys():
                dict = var_dicts[var_name]
                dict["name"] = var_name
                dict["template_directory"] = template_dir
                current_var = self.var_factory.get_config_variable(dict)
                current_var = ConfigGenerator.Node(current_var)
                current_var._set_parent(dict["depends_on"])
                current_var._set_iters(dict["num_iters"])
                current_var._set_reset_bool(dict["resets"])
                current_var._set_child(None)
                vars.append(current_var)
            return vars

        def _create_node_assocations(self, vars):
            head = 0
            for node in range(len(vars)):
                if vars[node].parent is None and head != node:
                    vars[head]._set_parent(node)
                    vars[node]._set_child(head)
                    head = node
                elif vars[node].parent is not None and head != node:
                    parent = self._find_node(vars, vars[node].parent)
                    if vars[parent].child is None:
                        vars[parent]._set_child(node)
                        vars[node]._set_parent(parent)
                elif vars[node].parent is not None and head == node:
                    parent = self._find_node(vars, vars[node].parent)
                    if vars[parent].child is None:
                        vars[parent]._set_child(node)
                        vars[node]._set_parent(parent)
                    head = parent
                else:  # node parent is None and node is head
                    continue
            return head

        def _find_node(self, vars, var_name):
            for node in range(len(vars)):
                if vars[node].var.name == var_name:
                    return node
            raise ValueError(f"node {var_name} could not be found")

        def _verify_and_sort_node_structure(self, head, vars):
            num_nodes = len(vars)
            current_node = vars[head]
            current_depth = 0
            sorted_vars = []
            while True:
                if current_depth == num_nodes:
                    raise ValueError(
                        "Incorrect variable node structure, more nodes than "
                        "variables (loop somewhere)"
                    )
                sorted_vars.append(current_node)
                current_depth += 1
                if current_node.child is None:
                    break
                current_node = vars[current_node.child]
            if current_depth != num_nodes:
                raise ValueError("Variable node structure is missing a link somewhere")
            return sorted_vars

    class Node:
        """
            Wrapper around a ConfigVariable that can be structured, with other nodes, to form a
            linked list used in creating variable iterations.
        """

        def __init__(self, config_variable):
            self.var = config_variable

        def _set_parent(self, parent):
            self.parent = parent

        def _set_child(self, child):
            self.child = child

        def _set_iters(self, num_iters):
            self.num_iters = num_iters

        def _set_total_iters(self, iters):
            self.total_iters = iters

        def _set_reset_bool(self, resets):
            if resets.lower() == "yes":
                self.resets = True
                return
            self.resets = False

        def _get_variable_list(self, size):
            var_list = []
            for i in range(0, size):
                if i % self.num_iters == 0 and self.resets:
                    self.var.reset()
                val = self.var.value
                target = self.var.target
                var_list.append({"target": target, "value": val})
            if self.var.sort:
                var_list = sorted(var_list, key=lambda x: x["value"])
            for var in var_list:
                var["value"] = self.var.prefix + str(var["value"]) + self.var.suffix
            return var_list

    class VariableFactory:
        """
        Contains a Factory for config variables and a class for each type of config variable that
        has been defined so far. New variable types should be mapped here when they are added.
        """

        def __init__(self):
            self.type_map = {
                "num": ConfigGenerator.NumConfigVariable,
                "ip": ConfigGenerator.IpConfigVariable,
                "str": ConfigGenerator.StrConfigVariable,
                "list": ConfigGenerator.ListConfigVariable,
            }

        def get_config_variable(self, dict):
            return self.type_map[dict["type"]](dict)

    class ConfigVariable(ABC):
        """
            base class. In order to make a new class, the subclass has to overwrite __next__().
            Depending on the specifics of that class, other functions may need to be modified.
            New variable types should inherit from this class.

            sort : used by wrapper classes to determine if lists of its values should be
                   sorted or not. Should be true for all but List types - the generation algorithm
                   depends on sorted values to work properly.
        """

        def __init__(self, dict):
            self.name = dict["name"]
            self.target = dict["target"]
            self.type = dict["type"]
            self.start = dict["start"]
            self.step = dict["step"]
            self.prefix = dict.get("prefix", "")
            self.suffix = dict.get("suffix", "")
            self._value = None
            self.sort = True

        @property
        def value(self):
            self.__next__()
            return self._value

        def reset(self):
            self._value = None

        def __iter__(self):
            self._value = self.start

        @abstractmethod
        def __next__(self):
            """
                this function should handle the iteration of self._value. By default, it must
                handle a general case and a case where self._value is None.
            """
            raise NotImplementedError()

    class NumConfigVariable(ConfigVariable):
        def __next__(self):
            if self._value is None:
                self.__iter__()
                return
            self._value += self.step

    class StrConfigVariable(ConfigVariable):
        def __init__(self, dict):
            super().__init__(dict)
            if self.start == "":
                self.start = "a"

        def __next__(self):
            if self._value is None:
                self.__iter__()
                return
            if self.step == "alphabet":
                self._value = self._value[:-1] + self._next_letter(self._value[-1])
            else:
                self._value += self.step

        def _next_letter(self, prev):
            # return next letter in alphabet or append an "a" if there is no "next" letter
            if not prev.isalpha():
                raise ValueError()
            if prev == "z":
                return prev + "a"
            elif prev == "Z":
                return prev + "A"
            else:
                return chr(ord(prev) + 1)

    class IpConfigVariable(ConfigVariable):
        def __iter__(self):
            self._value = ipaddress.ip_address(self.start)
            self.step = ipaddress.ip_address(self.step)

        def __next__(self):
            # raises ipaddress.AddressValueError if the IP is invalid
            if self._value is None:
                self.__iter__()
                return
            self._value += int(self.step)

    class ListConfigVariable(ConfigVariable):
        def __init__(self, dict):
            super().__init__(dict)
            self.index = 0
            self.sort = False
            if "values" in dict.keys():
                self.vars = dict["values"]
            elif "filename" in dict.keys() and "template_directory" in dict.keys():
                self.template_directory = dict["template_directory"]
                self.vars = self._create_list_from_file(dict["filename"])
            else:
                raise ValueError(
                    'when defining a list variable, must include either "values" or "filename"'
                )

        def __iter__(self):
            self.index = 0
            self._value = self.vars[self.index]

        def _create_list_from_file(self, filename):
            return [
                line.strip()
                for line in open(pathlib.Path(self.template_directory + filename), "r").readlines()
            ]

        def __next__(self):
            if self._value is None:
                self.__iter__()
                return
            self.index += 1
            self.index %= len(self.vars)
            self._value = self.vars[self.index]


class ConfigFormatter:
    """
    this class contains a set of functions that are useful for formatting plaintext configs so
    that they can be converted to valid netconf using the netconfconverter tool.

    "valid" plaintext has:
        no quotes
        all container keys on a separate line
        no leading whitespace, exactly one space between lvalue and rvalue
        no duplicated containers (e.g. can't have two router A's, must collapse them into one)
        no empty lines
        matching exits for every container
    """

    def remove_quotes(self, config):
        """
            Removes all single and double quotes from all strings in the given list.

            Args:
                config (list of strings): list of strings to be formatted
            
            Returns:
                list containing all input strings, sans all single/double quotes
        """

        def _rq(line):
            newline = ""
            for char in line:
                if char in "\"'":
                    continue
                newline += char
            return newline

        return [_rq(line) for line in config]

    def collapse_duplicate_config(self, config, delimiter=None):
        """
            Merges partially or wholly duplicated configs into a single, contiguous config.

            Args:
                config (list of strings): tab-spaced configuration, like 'show output running'.
                                            one line of config per list item.
                delimiter (string): a string that is concatenated to every "exit" in the config.
                                    Since exits are removed and re-added, a user can pass a string
                                    here if the function is not correctly determining what the
                                    delimiter is. By default, the function will use the delimiter
                                    found on the first "exit".
            
            Returns:
                list of strings with all duplicate config elements removed.
        """
        re_config, delimiter = self._remove_exits_from_config(config, delimiter)
        config_tree = self._make_tree(re_config)
        logger.debug(f"config length pre-collapse: {len(re_config)}")
        time_start = time.time()
        collapsed_tree = self._collapse(config_tree, 0, 0, self._tree())
        time_end = time.time()
        collapsed_config = self._add_exits_to_config(
            collapsed_tree.convert_tree_to_config_list(), delimiter
        )
        logger.debug(f"config length pre-collapse: {len(collapsed_config)}")
        logger.debug(f"collapse time: {time_end - time_start} seconds")
        return collapsed_config

    def format_whitespace(self, config):
        """
            Removes all leading and trailing whitespace, reduces all whitespace substrings to
            one space, and removes empty lines.

            Args:
                config (list of strings): tab-spaced configuration, like 'show output running'.
                                            one line of config per list item.
            
            Returns:
                list of strings with no trailing/leading whitespace, no large gaps, and no
                empty lines.
        """
        return [re.sub(" +", " ", line.strip(" ")) for line in config]

    def remove_empty_lines(self, config):
        """
            Removes empty lines from a config list.

            Args:
                config (list of strings): tab-spaced configuration, like 'show output running'.

            Returns:
                list of strings with no empty lines.
        """
        return [line for line in config if line.strip() != ""]

    def split_container_keys(self, config):
        # TODO: add this functionality
        # this requires reading in the datamodel to find container keys, and ensuring that
        # the config contains the correct keys for every container
        pass

    def _collapse(self, tree, x, y, new_tree):
        path_to_current_node = self._make_unary_tree_from_parents(tree, x, y)
        new_tree = self._merge_tree(path_to_current_node, new_tree)
        for child in tree.tree[x][y].children:
            new_tree = self._collapse(tree, x + 1, child, new_tree)
        return new_tree

    def _make_tree(self, config):
        tree = self._tree()
        indent_level_map = {}
        current_level = 0
        current_indent = -1
        for line in config:
            line_indent = self._count_whitespace(line)
            if current_indent == line_indent:
                parent = tree.tree[current_level - 1][-1]
                tree.add_node(line, parent)

            elif current_indent < line_indent:
                current_indent = line_indent
                parent = tree.tree[current_level][-1]
                tree.add_node(line, parent)
                current_level += 1
                indent_level_map[current_indent] = current_level

            elif current_indent > line_indent:
                current_indent = line_indent
                current_level = indent_level_map[current_indent]
                parent = tree.tree[current_level - 1][-1]
                tree.add_node(line, parent)
        return tree

    def _make_unary_tree_from_parents(self, tree, target_x, target_y):
        _, path = tree.find_path_to_node(target_x, target_y, path=[], current_x=0, current_y=0)
        return self._make_tree(path)

    def _merge_tree(self, existing, new):
        current_level = 0
        parent = None
        while current_level <= existing.lowest_level:
            if current_level > new.lowest_level:
                break
            found = False

            if parent:
                potential_matches = parent.children
            else:
                potential_matches = range(len(new.tree[current_level]))
            for node in potential_matches:
                if existing.tree[current_level][0].value == new.tree[current_level][node].value:
                    found = True
                    parent = new.tree[current_level][node]
                    break

            if not found:
                break
            current_level += 1

        while current_level <= existing.lowest_level:
            if current_level > new.lowest_level:
                new.add_new_level()
            child = new.add_node(existing.tree[current_level][0].value, parent)
            parent = child
            current_level += 1
        return new

    def _count_whitespace(self, line):
        whitespace = 0
        for char in line:
            if char == " ":
                whitespace += 1
            else:
                break
        return whitespace

    def _add_exits_to_config(self, config, delimiter):
        new_config = []
        indent_levels = []
        current_indent = -1
        for line in config:
            line_indent = self._count_whitespace(line)
            if current_indent == line_indent:
                new_config.append(line)
            elif current_indent < line_indent:
                new_config.append(line)
                current_indent = line_indent
                if current_indent not in indent_levels:
                    indent_levels.append(current_indent)
            elif current_indent > line_indent:
                for level in reversed(indent_levels):
                    if level >= line_indent and level < current_indent:
                        new_config.append(" " * level + "exit" + delimiter)
                new_config.append(line)
                current_indent = line_indent
        if current_indent > 0:
            for level in reversed(indent_levels):
                if level >= 0 and level < current_indent:
                    new_config.append(" " * level + "exit" + delimiter)
        return new_config

    def _remove_exits_from_config(self, config, delimiter=None):
        if not delimiter:
            for line in config:
                line = line.strip()
                if line == "exit":
                    delimiter = line[line.find("exit") + 4 :]
                    break
        return [line for line in config if line.strip() != "exit"], delimiter

    class _tree:
        def __init__(self):
            self.tree = [[ConfigFormatter._treenode("", 0)]]
            self.print_spacing = 2

        @property
        def lowest_level(self):
            return len(self.tree) - 1

        @property
        def head(self):
            return self.tree[0][0]

        def __str__(self):
            output = ""
            for level in range(len(self.tree)):
                indent = level * self.print_spacing * " "
                for node in self.tree[level]:
                    output += f"{indent}{node}\n"
            return output

        def add_new_level(self):
            self.tree.append([])

        def add_node(self, value, parent):
            if parent.tree_level == self.lowest_level:
                self.add_new_level()
            child_level = parent.tree_level + 1
            self.tree[child_level].append(ConfigFormatter._treenode(value, child_level))
            parent.add_child(len(self.tree[child_level]) - 1)

        def find_path_to_node(self, target_x, target_y, path, current_x, current_y):
            node = self.tree[current_x][current_y]
            path.append(node.value)
            if current_x == target_x and current_y == target_y:
                return True, path[1:]
            for child in node.children:
                found, returned_path = self.find_path_to_node(
                    target_x, target_y, path, current_x + 1, child
                )
                if found:
                    return True, returned_path
            path.pop()
            return False, []

        def convert_tree_to_config_list(self):
            config_list = []
            if len(self.tree) == 0 or len(self.tree[0]) == 0:
                return []
            x = 0
            node_stack = [
                self.tree[self.head.tree_level + 1][child] for child in reversed(self.head.children)
            ]
            while len(node_stack) > 0:
                current = node_stack.pop()
                config_list.append(current.value)
                for child in reversed(current.children):
                    node_stack.append(self.tree[current.tree_level + 1][child])
            return config_list

    class _treenode:
        def __init__(self, value, tree_level):
            self.value = value
            self.children = []
            self.tree_level = tree_level

        def add_child(self, child_index):
            self.children.append(child_index)

        def __str__(self):
            if self.value.strip() == "":
                return f"<empty> {self.children}"
            return f"{self.value.strip()} {self.children}"
