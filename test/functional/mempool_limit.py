#!/usr/bin/env python3
# Copyright (c) 2014-2019 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test mempool limiting together/eviction with the wallet."""

from decimal import Decimal
from test_framework.blocktools import COINBASE_MATURITY

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import assert_equal, assert_greater_than, assert_raises_rpc_error, gen_return_txouts
from test_framework.wallet import MiniWallet
from test_framework.messages import CTransaction, from_hex

class MempoolLimitTest(BitcoinTestFramework):
    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 1
        self.extra_args = [[
            "-acceptnonstdtxn=1",
            "-maxmempool=5",
            "-spendzeroconfchange=0",
        ]]
        self.supports_cli = False

    def run_test(self):
        txouts = gen_return_txouts()
        # Helper function that generates large transactions

        node = self.nodes[0]
        miniwallet = MiniWallet(node)
        relayfee = node.getnetworkinfo()['relayfee']

        self.log.info('Check that mempoolminfee is minrelytxfee')
        assert_equal(node.getmempoolinfo()['minrelaytxfee'], Decimal('0.00001000'))
        assert_equal(node.getmempoolinfo()['mempoolminfee'], Decimal('0.00001000'))

        tx_ids=[]
        miniwallet.generate(1 + (3*30) + 1)
        # We generate 92 Coinbase UTXOs here because we need
        # 1 to create a tx that will be evicted from the mempool later
        # 30 with a fee higher than the previous UTXO
        # Another 30 with a fee higher than the previous set of UTXOs
        # Another 30 with a fee even higher than  the previous set of UTXOs
        # And 1 more to verify that this tx does not get added to the mempool with a relayfee (fee less than the mempoolminfee)

        node.generate(COINBASE_MATURITY - 1)
        # We mine 99 blocks so that we are allowed to spend our UTXOs
        

        self.log.info('Create a mempool tx that will be evicted')
        tx_to_be_evicted_id = miniwallet.send_self_transfer(from_node = node, fee_rate = relayfee)['txid']

        base_fee = relayfee*1000
        # We increase the tx fee massively now to give these transactions a higher priority in the mempool

        for batch_of_txid in range (3):
            tx_ids.append([])
            tx_ids[batch_of_txid] = self.create_large_transactions(node, txouts, miniwallet, 30, (batch_of_txid+1)*base_fee)
            # We gradually increase the tx fee by incrementing it by a factor of (basee_fee) for each batch of 30 transactions

        self.log.info('The tx should be evicted by now')
        assert_greater_than(len([txid for batch in tx_ids for txid in batch]), len(node.getrawmempool()))
        # We assert that the number of created transactions is greater than the ones in the mempool
        assert tx_to_be_evicted_id not in node.getrawmempool() 
        # We assert that our initial tx_to_be_evicted_id is not present in the mempool anymore as it's fee was less

        self.log.info('Check that mempoolminfee is larger than minrelytxfee')
        assert_equal(node.getmempoolinfo()['minrelaytxfee'], Decimal('0.00001000'))
        assert_greater_than(node.getmempoolinfo()['mempoolminfee'], Decimal('0.00001000'))

        self.log.info('Create a mempool tx that will not pass mempoolminfee')
        # We deliberately create a tx with a fee less that the minimum mempool fee to assert that it does not get added to the mempool
        assert_raises_rpc_error(-26, "mempool min fee not met", miniwallet.send_self_transfer, from_node=node, fee_rate=relayfee,mempool_valid=False)

    def create_large_transactions(self, node, array_of_large_tx, miniwallet, no_of_tx_ids, fee_rate):
    # This helper function is used to create large transactions by splicing in "txouts"
        large_txids = []
        for _ in range(no_of_tx_ids):
        # Loop that gives us a list of size num of large transaction IDs 
            tx = miniwallet.create_self_transfer(from_node=node, fee_rate=fee_rate)
            # We create a self transfer here and get the tx details
            hex=tx['hex']
            tx_instance = from_hex(CTransaction(), hex)
            # We convert it into a CTransaction() instance
            for txout in array_of_large_tx:
                tx_instance.vout.append(txout)
            # We append the tx outs that we received from the gen_return_txouts() to our tx instance to increase the tx size
            tx_hex = tx_instance.serialize().hex()
            miniwallet.sendrawtransaction(from_node=self.nodes[0], tx_hex=tx_hex)
            # We now serialisze it and send the tx to the nodes

            large_txids.append(tx['txid'])
            # We now append this tx ID to our array of large tx IDs
        return large_txids

if __name__ == '__main__':
    MempoolLimitTest().main()