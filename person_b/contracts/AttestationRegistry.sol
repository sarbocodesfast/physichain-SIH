// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title AttestationRegistry
/// @notice Minimal on-chain log of device attestations for PhysiChain.
///         Deliberately small (2 functions) for a 1-day hackathon build.
///         No upgradability, no access control beyond msg.sender logging --
///         add those later if you have time, not before the core demo works.
contract AttestationRegistry {
    enum TrustState { TRUSTED, STRICT, ISOLATED }

    struct Attestation {
        string deviceId;
        uint256 timestamp;
        bytes32 attestationHash; // hash of the full off-chain JSON packet
        TrustState state;
        address submittedBy;
    }

    Attestation[] public attestations;

    event AttestationLogged(
        uint256 indexed index,
        string deviceId,
        TrustState state,
        bytes32 attestationHash
    );

    /// @notice Registers a device (call once per device before attesting)
    mapping(string => bool) public registeredDevices;

    function registerDevice(string calldata deviceId) external {
        registeredDevices[deviceId] = true;
    }

    /// @notice Logs one attestation packet's hash + trust state on-chain.
    /// @param deviceId The device identifier (must be pre-registered).
    /// @param attestationHash keccak256 hash of the off-chain JSON packet
    ///        (so the full packet doesn't need to live on-chain).
    /// @param state 0 = TRUSTED, 1 = STRICT, 2 = ISOLATED
    function logAttestation(
        string calldata deviceId,
        bytes32 attestationHash,
        TrustState state
    ) external {
        require(registeredDevices[deviceId], "device not registered");

        attestations.push(Attestation({
            deviceId: deviceId,
            timestamp: block.timestamp,
            attestationHash: attestationHash,
            state: state,
            submittedBy: msg.sender
        }));

        emit AttestationLogged(
            attestations.length - 1, deviceId, state, attestationHash
        );
    }

    function totalAttestations() external view returns (uint256) {
        return attestations.length;
    }
}
