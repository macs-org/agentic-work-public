// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract AIAuditTrail {
    struct Batch { bytes32 root; uint64 actionCount; uint64 committedAt; string uri; }
    address public owner;
    uint256 public batchCount;
    mapping(uint256 => Batch) public batches;
    mapping(bytes32 => bool) public knownRoots;
    event BatchCommitted(uint256 indexed batchId, bytes32 indexed root, uint64 actionCount, string uri);
    error NotOwner(); error InvalidActionCount(); error UnknownRoot();
    constructor() { owner = msg.sender; }
    modifier onlyOwner() { if (msg.sender != owner) revert NotOwner(); _; }
    function transferOwnership(address newOwner) external onlyOwner { owner = newOwner; }
    function commitBatch(bytes32 root, uint64 actionCount, string calldata uri) external onlyOwner returns (uint256 batchId) {
        if (actionCount == 0 || actionCount > 100) revert InvalidActionCount();
        batchId = ++batchCount;
        batches[batchId] = Batch({root: root, actionCount: actionCount, committedAt: uint64(block.timestamp), uri: uri});
        knownRoots[root] = true;
        emit BatchCommitted(batchId, root, actionCount, uri);
    }
    function verifyAction(bytes32 root, bytes32 leaf, bytes32[] calldata proof, uint256 index) public view returns (bool) {
        if (!knownRoots[root]) revert UnknownRoot();
        return computeRoot(leaf, proof, index) == root;
    }
    function computeRoot(bytes32 leaf, bytes32[] calldata proof, uint256 index) public pure returns (bytes32 h) {
        h = leaf;
        for (uint256 i = 0; i < proof.length; i++) {
            bytes32 p = proof[i];
            h = (index & 1 == 1) ? sha256(abi.encodePacked(p, h)) : sha256(abi.encodePacked(h, p));
            index >>= 1;
        }
    }
}
