#!/usr/bin/env python3
import click
import subprocess
import sys

# call it by: Apeiron xxx

@click.group(context_settings=dict(help_option_names=['-h', '--help']))
def cli():
    """Apeiron CLI tool for running configuration, node, and evolution commands."""
    pass

@cli.command(context_settings=dict(ignore_unknown_options=True, allow_extra_args=True), add_help_option=False)
@click.pass_context
def gui(ctx):
    """Run the Streamlit GUI"""
    cmd = ['streamlit', 'run', 'bin/app.py'] + ctx.args
    subprocess.run(cmd)

@cli.command(context_settings=dict(ignore_unknown_options=True, allow_extra_args=True), add_help_option=False)
@click.pass_context
def setup(ctx):
    """Setup the environment""" # bash scripts/setup_env.sh
    cmd = ['bash', 'scripts/setup_env.sh']
    subprocess.run(cmd)



if __name__ == '__main__':
    cli()

