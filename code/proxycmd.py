import dockercmd

def run_proxy(node, start_hash):
        public_ips = [str(ip) for ip in node.public_ips]
        args = '{} '.format(node.args) if node.args else ''
        return ('python main.py ' + args +
                '--ip-private ' + str(node.private_ip) + ' '
                '--ips-public ' + ' '.join(public_ips) +
                ' --start-hash=' + start_hash)


def get_best_public_block_hash(node):
        return dockercmd.exec_bash(node, 'python cli.py get_best_public_block_hash')
