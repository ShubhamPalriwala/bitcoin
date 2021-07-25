#!/usr/bin/env python3
# Copyright (c) 2014-2019 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test mempool limiting together/eviction with the wallet."""

from decimal import Decimal
from test_framework.blocktools import COINBASE_MATURITY

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import (
    assert_equal,
    assert_greater_than,
    assert_raises_rpc_error,
    gen_return_txouts,
)
from test_framework.wallet import MiniWallet


class MempoolLimitTest(BitcoinTestFramework):
    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 1
        self.extra_args = [
            [
                "-acceptnonstdtxn=1",
                "-maxmempool=5",
                "-spendzeroconfchange=0",
            ]
        ]
        self.supports_cli = False

    def run_test(self):
        txouts = gen_return_txouts()

        node = self.nodes[0]
        miniwallet = MiniWallet(node)
        relayfee = node.getnetworkinfo()["relayfee"]

        self.log.info("Check that mempoolminfee is minrelaytxfee")
        assert_equal(node.getmempoolinfo()["minrelaytxfee"], Decimal("0.00001000"))
        assert_equal(node.getmempoolinfo()["mempoolminfee"], Decimal("0.00001000"))

        # Generate 92 UTXOs to flood the mempool
        # 1 to create a tx initially that will be evicted from the mempool later
        # 90 with a fee rate much higher than the previous UTXO (3 batches of 30 with increasing fee rate)
        # And 1 more to verify that this tx does not get added to the mempool with a fee rate less than the mempoolminfee
        miniwallet.generate(1 + (3 * 30) + 1)

        # Mine 99 blocks so that the UTXOs are allowed to be spent
        node.generate(COINBASE_MATURITY - 1)

        self.log.info("Create a mempool tx that will be evicted")
        tx_to_be_evicted_id = miniwallet.send_self_transfer(
            from_node=node, fee_rate=relayfee
        )["txid"]

        # Increase the tx fee rate massively now to give the next transactions a higher priority in the mempool
        base_fee = relayfee * 1000

        self.log.info("Fill up the mempool with txs with higher fee rate")
        no_of_large_tx_created = 0
        for batch_of_txid in range(3):
            # Increment the tx fee rate gradually by a factor of (basee_fee) for each batch of 30 transactions
            no_of_large_tx_created += miniwallet.create_large_transactions(
                node, txouts, 30, (batch_of_txid + 1) * base_fee
            )

        self.log.info("The tx should be evicted by now")
        # The number of transactions created should be greater than the ones present in the mempool
        assert_greater_than(no_of_large_tx_created, len(node.getrawmempool()))
        # Initial tx created should not be present in the mempool anymore as it had a lower fee rate
        assert tx_to_be_evicted_id not in node.getrawmempool()

        self.log.info("Check that mempoolminfee is larger than minrelytxfee")
        assert_equal(node.getmempoolinfo()["minrelaytxfee"], Decimal("0.00001000"))
        assert_greater_than(
            node.getmempoolinfo()["mempoolminfee"], Decimal("0.00001000")
        )

        # Deliberately tries to create a tx with a fee less that the minimum mempool fee to assert that it does not get added to the mempool
        self.log.info("Create a mempool tx that will not pass mempoolminfee")
        assert_raises_rpc_error(
            -26,
            "mempool min fee not met",
            miniwallet.send_self_transfer,
            from_node=node,
            fee_rate=relayfee,
            mempool_valid=False,
        )


if __name__ == "__main__":
    MempoolLimitTest().main()
