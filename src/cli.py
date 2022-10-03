import argparse
from re import L
import sys
import os
import click
import toml
import traceback

from typing import Callable, Dict, List
from os import listdir
from os.path import isfile, join
from starkware.cairo.lang.compiler.ast.module import CairoFile, CairoModule
from starkware.cairo.lang.compiler.parser import parse_file
from starkware.cairo.lang.version import __version__

from starknet_interface_generator.generator import Generator
from starknet_interface_generator.interface_parser import InterfaceParser


def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo('Version 0.1.4')
    ctx.exit()


def generate_files(directory: str, files: List[str]):
    for path in files:
        contract_file = open(path).read()
        dirpath, filename = os.path.split(path)
        contract_name = filename.split(".")[0]
        newfilename = f"i_" + filename
        newpath = os.path.join(directory or dirpath, newfilename)

        try:

            # Generate the AST of the cairo contract, visit it and generate the interface
            contract = CairoModule(
                cairo_file=cairo_parser(contract_file, filename),
                module_name=path,
            )

            generator = Generator(dirpath, contract_name)
            contract_interface_str = generator.generate_contract_interface(
                contract)

            # Generate the AST from the cairo interface, format it, and write it to a file
            contract_interface = CairoModule(
                cairo_file=cairo_parser(contract_interface_str, newfilename),
                module_name=path,
            )
            formatted_interface = contract_interface.format()

        except Exception as exc:
            print(traceback.format_exc())
            return 1

        print(f"Generating interface {newpath}")
        open(newpath, "w").write(formatted_interface)


def check_files(directory, files):
    for path in files:
        contract_file = open(path).read()
        dirpath, filename = os.path.split(path)
        contract_name = filename.split(".")[0]
        interface_name = f"i_" + filename
        interface_path = f"{directory}/{interface_name}"
        tempfile_name = interface_name + ".tmp"
        try:
            interface_file = open(interface_path).read()
        except:
            print(
                f"Couldn't open corresponding interface file for {interface_path}")
            continue

        newpath = os.path.join(directory or dirpath, tempfile_name)

        try:

            # Generate the AST of the cairo contract, visit it and generate the interface
            contract = CairoModule(
                cairo_file=cairo_parser(contract_file, filename),
                module_name=path,
            )

            generator = Generator(dirpath, contract_name)
            contract_interface_str = generator.generate_contract_interface(
                contract)

            # Generate the AST from the cairo interface, format it, and write it to a file
            contract_interface = CairoModule(
                cairo_file=cairo_parser(
                    contract_interface_str, interface_name),
                module_name=path,
            )
            parsed_generated_interface = InterfaceParser(
                contract_name).parse_interface(contract_interface)

            existing_interface = CairoModule(
                cairo_file=cairo_parser(interface_file, tempfile_name),
                module_name=path,
            )
            parsed_existing_interface = InterfaceParser(
                contract_name).parse_interface(existing_interface)

            def check_name(generated: Dict, existing: Dict):
                if generated['name'] != existing['name']:
                    print(
                        f"Name mismatch between contract and interface for {contract_name}")

            def check_functions(source: Dict, comparison: Dict, source_is_correct):
                error_detail = "is missing from the interface" if source_is_correct else "is not in contract"
                for func_name in source:
                    if func_name not in comparison:
                        print(
                            f"Function <{func_name}> is missing from the interface for {contract_name}")
                        continue
                    source_params = source[func_name]['params']
                    for source_param in source_params:
                        if source_param not in comparison[func_name]['params']:
                            print(
                                f"Parameter <{source_param}> {error_detail} for {contract_name}:{func_name}")
                            continue
                    source_returns = source[func_name]['returns']
                    for source_return in source_returns:
                        if source_return not in comparison[func_name]['returns']:
                            print(
                                f"Return <{source_return}> {error_detail} for {contract_name}:{func_name}")
                            continue

            def check_imports(source: Dict, comparison: Dict, source_is_correct):
                error_detail = "is missing from the interface" if source_is_correct else "is not in contract"
                for import_name in source:
                    if import_name not in comparison:
                        print(
                            f"Import <{import_name}> {error_detail} for {contract_name}")
                        continue
                    source_path = source[import_name]
                    if source_path not in comparison[import_name]:
                        print(
                            f"Import path <{source_path}> {error_detail} for {contract_name}:{import_name}")
                        continue

            check_name(parsed_generated_interface, parsed_existing_interface)

            # Check if the existing interface has missing elements
            check_functions(parsed_generated_interface['functions'],
                            parsed_existing_interface['functions'], True)
            # Check if the existing interface has extra elements
            check_functions(
                parsed_existing_interface['functions'], parsed_generated_interface['functions'], False)

            check_imports(
                parsed_generated_interface['imports'], parsed_existing_interface['imports'], True)
            check_imports(
                parsed_existing_interface['imports'], parsed_generated_interface['imports'], False)
        except Exception as exc:
            print(traceback.format_exc())
            return 1


def cairo_parser(code, filename): return parse_file(
    code=code, filename=filename)


def get_contracts_from_protostar(protostar_path: str):
    config = toml.load(protostar_path)
    contracts = config['protostar.contracts']
    contracts_paths = [contract[0] for contract in contracts.values()]
    return contracts_paths


@click.group()
@click.option('--version', is_flag=True, callback=print_version,
              expose_value=False, is_eager=True)
def cli():
    pass


@click.command()
@click.option("--files", multiple=True, default=[], help="File names")
@click.option('--protostar', '-p', is_flag=True, help='Uses `protostar.toml` to get file names')
@click.option('--directory', '-d', help='Output directory for the interfaces. If unspecified, they will be created in the same directory as the contracts')
def generate(protostar: bool, directory: str, files: List[str]):
    if protostar:
        protostar_path = os.path.join(os.getcwd(), "protostar.toml")
        files = get_contracts_from_protostar(protostar_path)

    generate_files(directory, files)

    return 0


@click.command()
@click.option("--files", multiple=True, default=[], help="Contracts to check")
@click.option('--directory', '-d', help='Directory of the interfaces to check. Interfaces must be named `i_<contract_name>.cairo`')
def check(directory: str, files: List[str]):

    check_files(directory, files)

    return 0


cli.add_command(generate)
cli.add_command(check)


def main():
    cli()


if __name__ == "__main__":
    sys.exit(main())