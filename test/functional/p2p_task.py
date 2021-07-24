#!/usr/bin/env python3

from test_framework.messages import msg_tx
from test_framework.blocktools import COINBASE_MATURITY
from test_framework.p2p import P2PInterface
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import assert_equal
import pdb

class P2PAddConnections(BitcoinTestFramework):
    def set_test_params(self):
        self.setup_clean_chain=True
        self.num_nodes = 3

    def setup_network(self):
        self.setup_nodes()
    
    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def connect_nodes(self):
        
        self.log.info("Connecting 2 full-relay outbound connections")
        self.outbound_peer1=self.nodes[0].add_outbound_p2p_connection(P2PInterface(),p2p_idx=1,connection_type="outbound-full-relay")
        self.outbound_peer2=self.nodes[0].add_outbound_p2p_connection(P2PInterface(),p2p_idx=2,connection_type="outbound-full-relay")
            # node 0--> outbound_peer1
            #    |
            #    -----> outbound_peer2
        
        self.log.info("Connecting 1 inbound connection")
        self.inbound_peer1=self.nodes[0].add_p2p_connection(P2PInterface())
            # inbound_peer1 --> node 0--> outbound_peer1
            #                |
            #                -----------> outbound_peer2
        info = self.nodes[0].getnetworkinfo()

        self.log.info("Checking 1 in-bound and 2 out-bound connections")
        assert_equal(info["connections_in"], 1)
        assert_equal(info["connections_out"], 2)

    def create_transaction(self):
        self.log.info("Create and Relay the transaction")
        self.nodes[0].generate(COINBASE_MATURITY+1)
        node2_address=self.nodes[2].getnewaddress()
        self.txid=self.nodes[0].sendtoaddress(node2_address,10)

    def check_peers_received_tx(self):
        self.outbound_peer1.wait_for_tx(self.txid)
        # This confirms that the last message recd by the node
        # was this transaction id itself
        self.log.info("Outbound Peer 1 received transaction")

        self.outbound_peer2.wait_for_tx(self.txid)
        # This confirms that the last message recd by the node
        # was this transaction id itself
        self.log.info("Outbound Peer 2 received transaction")

        self.inbound_peer1.wait_for_tx(self.txid)
        # This confirms that the last message recd by the node
        # was this transaction id itself
        self.log.info("Inbound Peer 1 received transaction")
    
    def disconnect_from_nodes(self):
        self.nodes[0].disconnect_p2ps()
        # Disconnects all the P2P nodes from our self.nodes[0]
        assert_equal(len(self.nodes[0].getpeerinfo()),0)

    def run_test(self):
        self.connect_nodes()
        self.create_transaction()
        self.check_peers_received_tx()
        self.disconnect_from_nodes()

if __name__ == '__main__':
    P2PAddConnections().main()