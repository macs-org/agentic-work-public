// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Reference x402/Base USDC escrow for autonomous task assignments.
/// @dev Compact review artifact: wire to an audited token transfer adapter before production.
contract AgentTaskEscrow {
    enum State { None, Held, Released, Refunded }

    struct Escrow {
        address poster;
        address agent;
        uint256 amount;
        uint256 deadline;
        State state;
    }

    address public immutable usdc;
    uint256 public arbitrationFeeBps = 250; // 2.5%
    mapping(bytes32 => Escrow) public escrows;
    mapping(address => bytes32[]) public reputationAttestations;

    event EscrowHeld(bytes32 indexed taskId, address indexed poster, address indexed agent, uint256 amount, uint256 deadline);
    event EscrowReleased(bytes32 indexed taskId, address indexed agent, uint256 amount);
    event EscrowRefunded(bytes32 indexed taskId, address indexed poster, uint256 refundAmount, uint256 arbitrationFee);
    event ReputationAttested(address indexed agent, bytes32 indexed attestationUid);

    constructor(address usdc_) {
        usdc = usdc_;
    }

    function hold(bytes32 taskId, address agent, uint256 amount, uint256 deadline) external {
        require(escrows[taskId].state == State.None, "escrow exists");
        require(agent != address(0), "agent required");
        require(deadline > block.timestamp, "deadline in past");
        // Production x402 integration transfers USDC before/inside this call.
        escrows[taskId] = Escrow({poster: msg.sender, agent: agent, amount: amount, deadline: deadline, state: State.Held});
        emit EscrowHeld(taskId, msg.sender, agent, amount, deadline);
    }

    function release(bytes32 taskId) external {
        Escrow storage e = escrows[taskId];
        require(msg.sender == e.poster, "poster only");
        require(e.state == State.Held, "not held");
        e.state = State.Released;
        // Production implementation transfers USDC to e.agent here.
        emit EscrowReleased(taskId, e.agent, e.amount);
    }

    function refund(bytes32 taskId) external {
        Escrow storage e = escrows[taskId];
        require(msg.sender == e.poster || block.timestamp > e.deadline, "poster or expired only");
        require(e.state == State.Held, "not held");
        e.state = State.Refunded;
        uint256 fee = (e.amount * arbitrationFeeBps) / 10_000;
        emit EscrowRefunded(taskId, e.poster, e.amount - fee, fee);
    }

    function attestReputation(address agent, bytes32 attestationUid) external {
        require(agent != address(0), "agent required");
        reputationAttestations[agent].push(attestationUid);
        emit ReputationAttested(agent, attestationUid);
    }
}
