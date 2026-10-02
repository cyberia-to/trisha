"""Assemble, inspect and smoke portable compiler kits (release-platforms.md contract)."""
import argparse
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import selfhost_kit as K
from selfhost_kit_assembly import assemble


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('assemble', 'rehearse'):
        command = commands.add_parser(name)
        for key in ('trident', 'guide', 'work', 'output'):
            command.add_argument('--' + key, type=Path, required=True)
        for key in (('validator', 'config') if name == 'assemble' else ('compiler', 'inventory', 'fixed-point')):
            command.add_argument('--' + key, type=Path, required=True)
    command = commands.add_parser('unpack')
    for key in ('archive', 'output', 'trident'):
        command.add_argument('--' + key, type=Path, required=True)
    command.add_argument('--sha256', required=True)
    for name in ('smoke', 'check'):
        command = commands.add_parser(name)
        for key in ('kit', 'trident'):
            command.add_argument('--' + key, type=Path, required=True)
        command.add_argument('--rehearsal', action='store_true')
        command.add_argument('--joy', type=Path, required=name == 'smoke')
        command.add_argument('--receipt', type=Path)
        if name == 'smoke':
            command.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    for key, value in vars(args).items():
        if isinstance(value, Path):
            # Resolve parents for portable absolute subprocess paths, preserving
            # final symlinks so ordinary-file/output guards can reject them.
            setattr(args, key, value.parent.resolve() / value.name)
    if args.command in ('assemble', 'rehearse'):
        assemble(args)
    elif args.command == 'unpack':
        K.unpack(args.archive, args.sha256, args.output, args.trident)
    elif args.command == 'smoke':
        K.smoke(args.kit, args.joy, args.output, args.trident, args.rehearsal)
    else:
        K.check(args.kit, args.trident, args.rehearsal)
        if args.receipt:
            K.require(args.joy is not None and not args.rehearsal, 'production smoke requires Joy')
            K.check_smoke(args.kit, args.joy, args.receipt)


if __name__ == '__main__':
    main()
