import json
import os
import pytest

from ote_utils import config_gen


class ConfigGeneratorInputs:
    def __init__(self):
        self._basic_var = {
            "var": {
                "type": "num",
                "depends_on": None,
                "num_iters": 1,
                "target": "{{ var }}",
                "start": 1,
                "step": 1,
                "resets": "no",
                "prefix": "",
                "suffix": "",
            }
        }
        self._basic_template = ["template_start", "   var: {{ var }}", "exit"]
        self.basic_config = """
            config
                authority
                    router {{ router }}
                        name {{ router }}
                        node {{ node }}
                            name {{ node }}
                        exit
                    exit
                exit
            exit
            """.split(
            "\n"
        )
        self.node_config = """
            config
                authority
                    router          {{ router }}
                        name        {{ router }}
                        node        {{ node }}
                            name                    {{ node }}
                            description             "linecard-test node"
                            enabled                 true

                            device-interface        10
                                name               10
                                description        "device 1"
                                type               ethernet
                                pci-address        0000:14:00.1
                                network-interface  {{ intf_name }}
                                    name                   {{ intf_name }}
                                    global-id              1
                                    vlan                   0
                                    type                   external
                                    inter-router-security  interrouter
                                    rewrite-dscp           false
                                    source-nat             false
                                    qp-value               30
                                    mtu                    9198
                                    address                {{ intf_ip }}
                                        ip-address     {{ intf_ip }}
                                        prefix-length  28
                                        gateway        {{ intf_gw }}
                                    exit
                                exit
                            exit
                        exit
                    exit
                exit
            exit
            """.split(
            "\n"
        )
        self.prefix = ["prefix_line1", "prefix_line2", "prefix_line3"]
        self.suffix = ["suffix_line1", "suffix_line2", "suffix_line3"]

    def basic_var(self, **kwargs):
        return {"var": self.raw_var(**kwargs)}

    def basic_template(self, var="{{ var }}"):
        return [[line.replace("{{ var }}", var) for line in self._basic_template]]

    def raw_var(self, **kwargs):
        new_var = {}
        new_var.update(self._basic_var["var"])
        new_var.update(kwargs)
        return new_var


class ConfigGeneratorExpectedOutputs:
    def __init__(self):
        self.blank_bad_template = [
            ["template_start", "   var: {{ var }", "exit"],
            ["template_start", "   var: {{ var }", "exit"],
        ]
        self.basic_int_generation = [
            ["template_start", "   var: 1", "exit"],
            ["template_start", "   var: 2", "exit"],
        ]
        self.basic_str_generation_alpha = [
            ["template_start", "   var: aaa", "exit"],
            ["template_start", "   var: aab", "exit"],
        ]
        self.basic_str_generation_append = [
            ["template_start", "   var: aaa", "exit"],
            ["template_start", "   var: aaaa", "exit"],
        ]
        self.basic_ip_generation = [
            ["template_start", "   var: 192.168.0.1/24", "exit"],
            ["template_start", "   var: 192.168.1.1/24", "exit"],
        ]
        self.basic_list_generation = [
            ["template_start", "   var: value1", "exit"],
            ["template_start", "   var: value2", "exit"],
        ]
        self.complex_generated_config = (
            open(get_resource_path("config_gen/complex_generated_config"), "r").read().split("\n")
        )
        self.output_from_file = open(
            get_resource_path("config_gen/output_from_file"), "r"
        ).readlines()
        self.basic_collapsed_config = (
            open(get_resource_path("config_gen/basic_collapsed_config"), "r").read().split("\n")
        )
        self.complex_collapsed_config = (
            open(get_resource_path("config_gen/complex_collapsed_config"), "r").read().split("\n")
        )
        self.prefix_suffix_generation = [
            "prefix_line1",
            "prefix_line2",
            "prefix_line3",
            "template_start",
            "   var: value1",
            "   var: value2",
            "exit",
            "suffix_line1",
            "suffix_line2",
            "suffix_line3",
        ]


class ConfigGeneratorTestEnv:
    def __init__(self):
        self.c_g = config_gen.ConfigGenerator()
        self.c_f = config_gen.ConfigFormatter()
        self.inputs = ConfigGeneratorInputs()
        self.expected_outputs = ConfigGeneratorExpectedOutputs()


class TestConfigGenerator:
    def test_no_generation(self):
        test = ConfigGeneratorTestEnv()
        assert test.c_g.get_generated_config(flat=False) == []

    def test_default_generation(self):
        test = ConfigGeneratorTestEnv()
        test.c_g.generate_config()
        assert test.c_g.get_generated_config(flat=False) == []

    def test_basic_int_generation(self):
        test = ConfigGeneratorTestEnv()
        test.c_g.add_vars(test.inputs.basic_var(num_iters=2))
        test.c_g.add_templates(test.inputs.basic_template())
        test.c_g.set_copy_count(1)
        test.c_g.generate_config()
        assert (
            test.c_g.get_generated_config(flat=False) == test.expected_outputs.basic_int_generation
        )

    def test_file_write(self):
        test = ConfigGeneratorTestEnv()
        test.c_g.write_generated_config_to_file("tmp_output.txt")
        config = test.c_g.get_generated_config(flat=False)
        assert config == open("tmp_output.txt", "r").readlines()
        test.c_g.write_generated_config_to_file("tmp_output.txt")
        assert config + config == open("tmp_output.txt", "r").readlines()
        test.c_g.write_generated_config_to_file("tmp_output.txt", overwrite=True)
        assert config == open("tmp_output.txt", "r").readlines()
        os.unlink("tmp_output.txt")

    def test_reset(self):
        test = ConfigGeneratorTestEnv()
        test.c_g.add_vars(test.inputs.basic_var())
        test.c_g.add_templates(test.inputs.basic_template())
        test.c_g.generate_config()
        test.c_g.clear_vars()
        test.c_g.clear_templates()
        test.c_g.generate_config()
        assert test.c_g.get_generated_config(flat=False) == []

    def test_basic_str_generation(self):
        test = ConfigGeneratorTestEnv()
        test.c_g.add_vars(
            test.inputs.basic_var(type="str", start="aaa", step="alphabet", num_iters=2)
        )
        test.c_g.add_templates(test.inputs.basic_template())
        test.c_g.set_copy_count(1)
        test.c_g.generate_config()
        assert (
            test.c_g.get_generated_config(flat=False)
            == test.expected_outputs.basic_str_generation_alpha
        )
        test.c_g.add_vars(test.inputs.basic_var(type="str", start="aaa", step="a", num_iters=2))
        test.c_g.set_copy_count(1)
        test.c_g.generate_config()
        assert (
            test.c_g.get_generated_config(flat=False)
            == test.expected_outputs.basic_str_generation_append
        )

    def test_basic_ip_generation(self):
        test = ConfigGeneratorTestEnv()
        test.c_g.add_vars(
            test.inputs.basic_var(
                type="ip", start="192.168.0.1", step="0.0.1.0", suffix="/24", num_iters=2
            )
        )
        test.c_g.add_templates(test.inputs.basic_template())
        test.c_g.set_copy_count(1)
        test.c_g.generate_config()
        assert (
            test.c_g.get_generated_config(flat=False) == test.expected_outputs.basic_ip_generation
        )

    def test_basic_list_generation(self):
        test = ConfigGeneratorTestEnv()
        test.c_g.add_vars(
            test.inputs.basic_var(type="list", values=["value1", "value2"], num_iters=2)
        )
        test.c_g.add_templates(test.inputs.basic_template())
        test.c_g.set_copy_count(1)
        test.c_g.generate_config()
        assert (
            test.c_g.get_generated_config(flat=False) == test.expected_outputs.basic_list_generation
        )

    def test_basic_list_generation_from_file(self):
        test = ConfigGeneratorTestEnv()
        with open("list_values.txt", "w") as of:
            of.writelines(["value1\n", "value2"])
        test.c_g.add_vars(test.inputs.basic_var(type="list", filename="list_values.txt"))
        test.c_g.add_templates(test.inputs.basic_template())
        test.c_g.set_copy_count(2)
        test.c_g.generate_config()
        os.unlink("list_values.txt")
        assert (
            test.c_g.get_generated_config(flat=False) == test.expected_outputs.basic_list_generation
        )

    def test_basic_generation_bad_template(self):
        test = ConfigGeneratorTestEnv()
        test.c_g.add_vars(test.inputs.basic_var(num_iters=2))
        test.c_g.add_templates(test.inputs.basic_template(var="{{ var }"))
        test.c_g.set_copy_count(1)
        test.c_g.generate_config()
        assert test.c_g.get_generated_config(flat=False) == test.expected_outputs.blank_bad_template

    def test_complex_generation(self):
        test = ConfigGeneratorTestEnv()
        vars = {}
        vars["router"] = test.inputs.raw_var(target="{{ router }}", prefix="router")
        vars["node"] = test.inputs.raw_var(
            type="str",
            depends_on="router",
            num_iters=2,
            target="{{ node }}",
            start="A",
            step="alphabet",
            prefix="node-",
            resets="yes",
        )
        vars["net_int"] = test.inputs.raw_var(
            depends_on="node", num_iters=2, target="{{ intf_name }}", prefix="intf"
        )
        vars["ip"] = test.inputs.raw_var(
            type="ip",
            depends_on="net_int",
            target="{{ intf_ip }}",
            start="192.168.10.2",
            step="0.0.0.16",
            suffix="/28",
        )
        vars["gw"] = test.inputs.raw_var(
            type="ip",
            depends_on="ip",
            target="{{ intf_gw }}",
            start="192.168.10.1",
            step="0.0.0.16",
        )
        test.c_g.add_vars(vars)
        test.c_g.add_templates([test.inputs.node_config])
        test.c_g.set_copy_count(2)
        test.c_g.generate_config()
        assert test.c_g.get_generated_config() == test.expected_outputs.complex_generated_config

    def test_looped_variable_structure(self):
        test = ConfigGeneratorTestEnv()
        vars = {}
        vars["head"] = test.inputs.raw_var(depends_on="tail")
        vars["second"] = test.inputs.raw_var(depends_on="head")
        vars["third"] = test.inputs.raw_var(depends_on="second")
        vars["tail"] = test.inputs.raw_var(depends_on="third")
        with pytest.raises(ValueError) as exception_info:
            test.c_g.add_vars(vars)
        assert (
            "Incorrect variable node structure, more nodes than variables (loop somewhere)"
            in str(exception_info.value)
        )

    def test_disconnected_variable_structure(self):
        test = ConfigGeneratorTestEnv()
        vars = {}
        vars["head"] = test.inputs.raw_var()
        vars["second"] = test.inputs.raw_var(depends_on="head")
        vars["third"] = test.inputs.raw_var(depends_on="second")
        vars["tail"] = test.inputs.raw_var(depends_on="second")
        with pytest.raises(ValueError) as exception_info:
            test.c_g.add_vars(vars)
        assert "Variable node structure is missing a link somewhere" in str(exception_info.value)

    def test_variables_templates_from_file(self):
        test = ConfigGeneratorTestEnv()
        test.c_g.add_vars_from_file(get_resource_path("config_gen/vars.json"))
        test.c_g.add_templates_from_directory(get_resource_path("config_gen/"))
        test.c_g.set_copy_count(1)
        test.c_g.generate_config()
        assert test.c_g.get_generated_config() == test.expected_outputs.output_from_file

    def test_collapse_simple(self):
        test = ConfigGeneratorTestEnv()
        vars = {}
        vars["router"] = test.inputs.raw_var(target="{{ router }}", prefix="r")
        vars["node"] = test.inputs.raw_var(
            depends_on="router", num_iters=2, target="{{ node }}", resets="yes", prefix="n"
        )
        test.c_g.add_vars(vars)
        test.c_g.add_templates(test.inputs.basic_config)
        test.c_g.set_copy_count(1)
        test.c_g.generate_config()
        uncollapsed = test.c_g.get_generated_config()
        collapsed = test.c_f.collapse_duplicate_config(uncollapsed)
        assert collapsed == test.expected_outputs.basic_collapsed_config

    def test_collapse_complex(self):
        test = ConfigGeneratorTestEnv()
        vars = {}
        vars["router"] = test.inputs.raw_var(target="{{ router }}", prefix="router")
        vars["node"] = test.inputs.raw_var(
            type="str",
            depends_on="router",
            num_iters=2,
            target="{{ node }}",
            start="A",
            step="alphabet",
            prefix="node-",
            resets="yes",
        )
        vars["net_int"] = test.inputs.raw_var(
            depends_on="node", num_iters=2, target="{{ intf_name }}", prefix="intf"
        )
        vars["ip"] = test.inputs.raw_var(
            type="ip",
            depends_on="net_int",
            target="{{ intf_ip }}",
            start="192.168.10.2",
            step="0.0.0.16",
            suffix="/28",
        )
        vars["gw"] = test.inputs.raw_var(
            type="ip",
            depends_on="ip",
            target="{{ intf_gw }}",
            start="192.168.10.1",
            step="0.0.0.16",
        )
        test.c_g.add_vars(vars)
        test.c_g.add_templates([test.inputs.node_config])
        test.c_g.set_copy_count(2)
        test.c_g.generate_config()
        uncollapsed = test.c_g.get_generated_config()
        collapsed = test.c_f.collapse_duplicate_config(uncollapsed)
        assert collapsed == test.expected_outputs.complex_collapsed_config

    def test_template_prefix_suffix(self):
        test = ConfigGeneratorTestEnv()
        test.c_g.add_vars(test.inputs.basic_var(num_iters=2, prefix="value"))
        test.c_g.add_templates(test.inputs.basic_template())
        test.c_g.set_copy_count(1)
        test.c_g.add_config_prefix(test.inputs.prefix)
        test.c_g.add_config_suffix(test.inputs.suffix)
        test.c_g.generate_config()
        uncollapsed = test.c_g.get_generated_config()
        collapsed = test.c_f.collapse_duplicate_config(uncollapsed)
        assert collapsed == test.expected_outputs.prefix_suffix_generation


def get_resource_path(resource_filename):
    return os.path.join(os.path.dirname(__file__), "resources", resource_filename)
