"""
abstract: Tests full blob type transactions for [EIP-4844: Shard Blob Transactions](https://eips.ethereum.org/EIPS/eip-4844)

    Test full blob type transactions for [EIP-4844: Shard Blob Transactions](https://eips.ethereum.org/EIPS/eip-4844).

"""  # noqa: E501
from typing import Dict, List, Optional

import pytest

from ethereum_test_tools import (
    Account,
    Block,
    BlockchainTestFiller,
    Environment,
    Header,
    TestAddress,
    Transaction,
    to_address,
)

from .common import (
    BYTES_PER_FIELD_ELEMENT,
    DATA_GAS_PER_BLOB,
    FIELD_ELEMENTS_PER_BLOB,
    INF_POINT,
    MAX_BLOBS_PER_BLOCK,
    REF_SPEC_4844_GIT_PATH,
    REF_SPEC_4844_VERSION,
    Blob,
    calc_excess_data_gas,
    get_data_gasprice,
)

REFERENCE_SPEC_GIT_PATH = REF_SPEC_4844_GIT_PATH
REFERENCE_SPEC_VERSION = REF_SPEC_4844_VERSION


@pytest.fixture
def destination_account() -> str:
    """Default destination account for the blob transactions."""
    return to_address(0x100)


@pytest.fixture
def tx_value() -> int:
    """
    Default value contained by the transactions sent during test.

    Can be overloaded by a test case to provide a custom transaction value.
    """
    return 1


@pytest.fixture
def tx_gas() -> int:
    """Default gas allocated to transactions sent during test."""
    return 21000


@pytest.fixture
def tx_calldata() -> bytes:
    """Default calldata in transactions sent during test."""
    return b""


@pytest.fixture
def block_fee_per_gas() -> int:
    """Default max fee per gas for transactions sent during test."""
    return 7


@pytest.fixture(autouse=True)
def parent_excess_blobs() -> int:
    """
    Default excess blobs of the parent block.

    Can be overloaded by a test case to provide a custom parent excess blob
    count.
    """
    return 10  # Defaults to a data gas price of 1.


@pytest.fixture(autouse=True)
def parent_blobs() -> int:
    """
    Default data blobs of the parent blob.

    Can be overloaded by a test case to provide a custom parent blob count.
    """
    return 0


@pytest.fixture
def parent_excess_data_gas(
    parent_excess_blobs: int,
) -> int:
    """
    Calculates the excess data gas of the paraent block from the excess blobs.
    """
    return parent_excess_blobs * DATA_GAS_PER_BLOB


@pytest.fixture
def data_gasprice(
    parent_excess_data_gas: int,
    parent_blobs: int,
) -> int:
    """
    Data gas price for the block of the test.
    """
    return get_data_gasprice(
        excess_data_gas=calc_excess_data_gas(
            parent_excess_data_gas=parent_excess_data_gas,
            parent_blobs=parent_blobs,
        ),
    )


@pytest.fixture
def tx_max_priority_fee_per_gas() -> int:
    """
    Default max priority fee per gas for transactions sent during test.

    Can be overloaded by a test case to provide a custom max priority fee per
    gas.
    """
    return 0


@pytest.fixture
def txs_versioned_hashes(txs_blobs: List[List[Blob]]) -> List[List[bytes]]:
    """
    List of blob versioned hashes derived from the blobs.
    """
    return [[blob.versioned_hash() for blob in blob_tx] for blob_tx in txs_blobs]


@pytest.fixture(autouse=True)
def tx_max_fee_per_gas(
    block_fee_per_gas: int,
) -> int:
    """
    Max fee per gas value used by all transactions sent during test.

    By default the max fee per gas is the same as the block fee per gas.

    Can be overloaded by a test case to test rejection of transactions where
    the max fee per gas is insufficient.
    """
    return block_fee_per_gas


@pytest.fixture
def tx_max_fee_per_data_gas(  # noqa: D103
    data_gasprice: Optional[int],
) -> int:
    """
    Default max fee per data gas for transactions sent during test.

    By default, it is set to the data gas price of the block.

    Can be overloaded by a test case to test rejection of transactions where
    the max fee per data gas is insufficient.
    """
    if data_gasprice is None:
        # When fork transitioning, the default data gas price is 1.
        return 1
    return data_gasprice


@pytest.fixture
def tx_error() -> Optional[str]:
    """
    Default expected error produced by the block transactions (no error).

    Can be overloaded on test cases where the transactions are expected
    to fail.
    """
    return None


@pytest.fixture(autouse=True)
def txs(  # noqa: D103
    destination_account: Optional[str],
    tx_gas: int,
    tx_value: int,
    tx_calldata: bytes,
    tx_max_fee_per_gas: int,
    tx_max_fee_per_data_gas: int,
    tx_max_priority_fee_per_gas: int,
    txs_versioned_hashes: List[List[bytes]],
    tx_error: Optional[str],
    txs_blobs: List[List[Blob]],
    txs_wrapped_blobs: List[bool],
) -> List[Transaction]:
    """
    Prepare the list of transactions that are sent during the test.
    """
    if len(txs_blobs) != len(txs_versioned_hashes) or len(txs_blobs) != len(txs_wrapped_blobs):
        raise ValueError("txs_blobs and txs_versioned_hashes should have the same length")
    txs: List[Transaction] = []
    nonce = 0
    for tx_blobs, tx_versioned_hashes, tx_wrapped_blobs in zip(
        txs_blobs, txs_versioned_hashes, txs_wrapped_blobs
    ):
        blobs_info = Blob.blobs_to_transaction_input(tx_blobs)
        txs.append(
            Transaction(
                ty=3,
                nonce=nonce,
                to=destination_account,
                value=tx_value,
                gas_limit=tx_gas,
                data=tx_calldata,
                max_fee_per_gas=tx_max_fee_per_gas,
                max_priority_fee_per_gas=tx_max_priority_fee_per_gas,
                max_fee_per_data_gas=tx_max_fee_per_data_gas,
                access_list=[],
                blob_versioned_hashes=tx_versioned_hashes,
                error=tx_error,
                blobs=blobs_info[0],
                blob_kzg_commitments=blobs_info[1],
                blob_kzg_proofs=blobs_info[2],
                wrapped_blob_transaction=tx_wrapped_blobs,
            )
        )
        nonce += 1
    return txs


@pytest.fixture
def pre() -> Dict:
    """
    Prepares the pre state of all test cases, by setting the balance of the
    source account of all test transactions.
    """
    return {
        TestAddress: Account(balance=10**40),
    }


@pytest.fixture
def env(
    parent_excess_data_gas: int,
) -> Environment:
    """
    Prepare the environment for all test cases.
    """
    return Environment(
        excess_data_gas=parent_excess_data_gas,
        data_gas_used=0,
    )


@pytest.fixture
def blocks(
    txs: List[Transaction],
    tx_error: Optional[str],
) -> List[Block]:
    """
    Prepare the list of blocks for all test cases.
    """
    header_data_gas_used = 0
    if len(txs) > 0:
        header_data_gas_used = (
            sum(
                [
                    len(tx.blob_versioned_hashes)
                    for tx in txs
                    if tx.blob_versioned_hashes is not None
                ]
            )
            * DATA_GAS_PER_BLOB
        )
    return [
        Block(txs=txs, exception=tx_error, rlp_modifier=Header(data_gas_used=header_data_gas_used))
    ]


@pytest.mark.parametrize(
    "txs_blobs,txs_wrapped_blobs",
    [
        (
            [  # Txs
                [  # Blobs per transaction
                    Blob(
                        blob=bytes(FIELD_ELEMENTS_PER_BLOB * BYTES_PER_FIELD_ELEMENT),
                        kzg_commitment=INF_POINT,
                        kzg_proof=INF_POINT,
                    ),
                ]
            ],
            [True],
        ),
        (
            [  # Txs
                [  # Blobs per transaction
                    Blob(
                        blob=bytes(FIELD_ELEMENTS_PER_BLOB * BYTES_PER_FIELD_ELEMENT),
                        kzg_commitment=INF_POINT,
                        kzg_proof=INF_POINT,
                    )
                ]
                for _ in range(MAX_BLOBS_PER_BLOCK)
            ],
            [True] + ([False] * (MAX_BLOBS_PER_BLOCK - 1)),
        ),
        (
            [  # Txs
                [  # Blobs per transaction
                    Blob(
                        blob=bytes(FIELD_ELEMENTS_PER_BLOB * BYTES_PER_FIELD_ELEMENT),
                        kzg_commitment=INF_POINT,
                        kzg_proof=INF_POINT,
                    )
                ]
                for _ in range(MAX_BLOBS_PER_BLOCK)
            ],
            ([False] * (MAX_BLOBS_PER_BLOCK - 1)) + [True],
        ),
    ],
    ids=[
        "one_full_blob_one_tx",
        "one_full_blob_max_txs",
        "one_full_blob_at_the_end_max_txs",
    ],
)
@pytest.mark.valid_from("Cancun")
def test_reject_valid_full_blob_in_block_rlp(
    blockchain_test: BlockchainTestFiller,
    pre: Dict,
    env: Environment,
    blocks: List[Block],
):
    """
    Test valid blob combinations where one or more txs in the block
    serialized version contain a full blob (network version) tx.
    """
    blockchain_test(
        pre=pre,
        post={},
        blocks=blocks,
        genesis_environment=env,
    )