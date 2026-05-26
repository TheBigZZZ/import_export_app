import cyclonedx_py._internal.cli as cli

if __name__ == '__main__':
    import sys
    # Use the 'requirements' subcommand to read pinned requirements file
    sys.argv = ['cyclonedx-py', 'requirements', 'packaging/requirements-pinned.txt', '-o', 'packaging/sbom.xml']
    cli.run()
    print('sbom generated')
