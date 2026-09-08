// SPDX-License-Identifier: MIT
pragma solidity 0.8.36;

import {Script} from "forge-std/Script.sol";
import {TechtreeGraphRegistryV1} from "../../src/techtree/TechtreeGraphRegistryV1.sol";

contract DeployTechtreeGraphRegistryV1BaseMainnet is Script {
    error WrongChain(uint256 actualChainId);
    error RolesNotDistinct(address deployer, address owner, address registrar);

    /// @notice Prepares a Base mainnet deployment from environment-provided role addresses and key.
    /// @dev Run only with explicit founder authorization. Required environment variables are
    ///      DEPLOYER_PRIVATE_KEY, TECHTREE_OWNER, and TECHTREE_REGISTRAR.
    function run() external returns (TechtreeGraphRegistryV1 deployed) {
        if (block.chainid != 8453) revert WrongChain(block.chainid);
        uint256 deployerPrivateKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address initialOwner = vm.envAddress("TECHTREE_OWNER");
        address initialRegistrar = vm.envAddress("TECHTREE_REGISTRAR");
        address deployer = vm.addr(deployerPrivateKey);
        _requireDistinctRoles(deployer, initialOwner, initialRegistrar);

        vm.startBroadcast(deployerPrivateKey);
        deployed = new TechtreeGraphRegistryV1(initialOwner, initialRegistrar);
        vm.stopBroadcast();
    }

    function _requireDistinctRoles(address deployer, address initialOwner, address initialRegistrar)
        internal
        pure
    {
        if (
            deployer == initialOwner || deployer == initialRegistrar
                || initialOwner == initialRegistrar
        ) revert RolesNotDistinct(deployer, initialOwner, initialRegistrar);
    }
}
