// SPDX-License-Identifier: MIT
pragma solidity 0.8.36;

import {Test} from "forge-std/Test.sol";
import {TechtreeGraphRegistryV1} from "../../src/techtree/TechtreeGraphRegistryV1.sol";
import {
    DeployTechtreeGraphRegistryV1BaseSepolia
} from "../../script/techtree/DeployTechtreeGraphRegistryV1BaseSepolia.s.sol";
import {
    DeployTechtreeGraphRegistryV1BaseMainnet
} from "../../script/techtree/DeployTechtreeGraphRegistryV1BaseMainnet.s.sol";

contract BaseSepoliaDeployHarness is DeployTechtreeGraphRegistryV1BaseSepolia {
    function requireDistinctRoles(address deployer, address initialOwner, address initialRegistrar)
        external
        pure
    {
        _requireDistinctRoles(deployer, initialOwner, initialRegistrar);
    }
}

contract BaseMainnetDeployHarness is DeployTechtreeGraphRegistryV1BaseMainnet {
    function requireDistinctRoles(address deployer, address initialOwner, address initialRegistrar)
        external
        pure
    {
        _requireDistinctRoles(deployer, initialOwner, initialRegistrar);
    }
}

contract TechtreeGraphRegistryV1Test is Test {
    TechtreeGraphRegistryV1 internal registry;

    address internal constant OWNER = address(0xA11CE);
    address internal constant REGISTRAR = address(0xB0B);
    address internal constant OTHER = address(0xCAFE);

    bytes32 internal constant TREE = bytes32(uint256(1));
    bytes32 internal constant ROOT = bytes32(uint256(2));
    bytes32 internal constant CHILD = bytes32(uint256(3));
    bytes32 internal constant EDGE = bytes32(uint256(4));
    bytes32 internal constant REVISION = bytes32(uint256(5));
    bytes32 internal constant NEXT_REVISION = bytes32(uint256(6));
    bytes32 internal constant THIRD = bytes32(uint256(7));
    bytes32 internal constant KIND = bytes32(uint256(11));

    event OwnershipTransferStarted(address indexed previousOwner, address indexed pendingOwner);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event RegistrarUpdated(address indexed previousRegistrar, address indexed newRegistrar);
    event TreeRegistered(bytes32 indexed treeUid, TechtreeGraphRegistryV1.TreeStatus status);
    event TreeStatusUpdated(
        bytes32 indexed treeUid,
        TechtreeGraphRegistryV1.TreeStatus previousStatus,
        TechtreeGraphRegistryV1.TreeStatus status
    );
    event NodeRegistered(
        bytes32 indexed nodeUid,
        bytes32 revisionUid,
        bytes32 indexed treeUid,
        bytes32 indexed parentNodeUid,
        bytes32 nodeKind,
        address publisherRegistry,
        bytes32 publisherAgentId,
        uint256 publisherTokenId,
        TechtreeGraphRegistryV1.NodeStatus status,
        bytes32 supersededBy
    );
    event NodeStatusUpdated(
        bytes32 indexed nodeUid,
        bytes32 revisionUid,
        bytes32 indexed treeUid,
        bytes32 indexed parentNodeUid,
        bytes32 nodeKind,
        address publisherRegistry,
        bytes32 publisherAgentId,
        uint256 publisherTokenId,
        TechtreeGraphRegistryV1.NodeStatus previousStatus,
        TechtreeGraphRegistryV1.NodeStatus status,
        bytes32 supersededBy
    );
    event NodeRevisionRegistered(
        bytes32 indexed nodeUid, bytes32 previousRevisionUid, bytes32 newRevisionUid
    );
    event EdgeRegistered(
        bytes32 indexed edgeUid,
        bytes32 indexed fromNodeUid,
        bytes32 indexed toNodeUid,
        TechtreeGraphRegistryV1.EdgeKind kind,
        TechtreeGraphRegistryV1.EdgeStatus status
    );
    event EdgeStatusUpdated(
        bytes32 indexed edgeUid,
        bytes32 indexed fromNodeUid,
        bytes32 indexed toNodeUid,
        TechtreeGraphRegistryV1.EdgeKind kind,
        TechtreeGraphRegistryV1.EdgeStatus previousStatus,
        TechtreeGraphRegistryV1.EdgeStatus status
    );

    function setUp() public {
        registry = new TechtreeGraphRegistryV1(OWNER, REGISTRAR);
    }

    function testConstructorSetsRoles() public view {
        assertEq(registry.owner(), OWNER);
        assertEq(registry.registrar(), REGISTRAR);
        assertEq(registry.pendingOwner(), address(0));
        assertEq(registry.MAX_BATCH_SIZE(), 100);
    }

    function testConstructorRejectsZeroOwner() public {
        vm.expectRevert(TechtreeGraphRegistryV1.ZeroAddress.selector);
        new TechtreeGraphRegistryV1(address(0), REGISTRAR);
    }

    function testConstructorRejectsZeroRegistrar() public {
        vm.expectRevert(TechtreeGraphRegistryV1.ZeroAddress.selector);
        new TechtreeGraphRegistryV1(OWNER, address(0));
    }

    function testConstructorRejectsOwnerRegistrarCollision() public {
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RoleCollision.selector, OWNER)
        );
        new TechtreeGraphRegistryV1(OWNER, OWNER);
    }

    function testTwoStepOwnershipTransfer() public {
        vm.expectEmit(true, true, false, true, address(registry));
        emit OwnershipTransferStarted(OWNER, OTHER);
        vm.prank(OWNER);
        registry.transferOwnership(OTHER);
        assertEq(registry.pendingOwner(), OTHER);
        assertEq(registry.owner(), OWNER);

        vm.expectEmit(true, true, false, true, address(registry));
        emit OwnershipTransferred(OWNER, OTHER);
        vm.prank(OTHER);
        registry.acceptOwnership();
        assertEq(registry.owner(), OTHER);
        assertEq(registry.pendingOwner(), address(0));
    }

    function testOwnershipTransferReverts() public {
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.Unauthorized.selector, OTHER)
        );
        vm.prank(OTHER);
        registry.transferOwnership(OTHER);

        vm.expectRevert(TechtreeGraphRegistryV1.ZeroAddress.selector);
        vm.prank(OWNER);
        registry.transferOwnership(address(0));

        vm.expectRevert(TechtreeGraphRegistryV1.OwnerUnchanged.selector);
        vm.prank(OWNER);
        registry.transferOwnership(OWNER);

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RoleCollision.selector, REGISTRAR)
        );
        vm.prank(OWNER);
        registry.transferOwnership(REGISTRAR);

        vm.prank(OWNER);
        registry.transferOwnership(OTHER);
        vm.expectRevert(TechtreeGraphRegistryV1.OwnerUnchanged.selector);
        vm.prank(OWNER);
        registry.transferOwnership(OTHER);

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.Unauthorized.selector, REGISTRAR)
        );
        vm.prank(REGISTRAR);
        registry.acceptOwnership();
    }

    function testOwnerRotatesRegistrar() public {
        vm.expectEmit(true, true, false, true, address(registry));
        emit RegistrarUpdated(REGISTRAR, OTHER);
        vm.prank(OWNER);
        registry.setRegistrar(OTHER);

        assertEq(registry.registrar(), OTHER);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.Unauthorized.selector, REGISTRAR)
        );
        vm.prank(REGISTRAR);
        registry.registerTree(TREE);
        vm.prank(OTHER);
        registry.registerTree(TREE);
    }

    function testRegistrarRotationReverts() public {
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.Unauthorized.selector, OTHER)
        );
        vm.prank(OTHER);
        registry.setRegistrar(OTHER);

        vm.expectRevert(TechtreeGraphRegistryV1.ZeroAddress.selector);
        vm.prank(OWNER);
        registry.setRegistrar(address(0));

        vm.expectRevert(TechtreeGraphRegistryV1.RegistrarUnchanged.selector);
        vm.prank(OWNER);
        registry.setRegistrar(REGISTRAR);

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RoleCollision.selector, OWNER)
        );
        vm.prank(OWNER);
        registry.setRegistrar(OWNER);

        vm.prank(OWNER);
        registry.transferOwnership(OTHER);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RoleCollision.selector, OTHER)
        );
        vm.prank(OWNER);
        registry.setRegistrar(OTHER);
    }

    function testBaseSepoliaDeployRequiresThreeDistinctRoles() public {
        BaseSepoliaDeployHarness harness = new BaseSepoliaDeployHarness();
        harness.requireDistinctRoles(address(1), address(2), address(3));

        vm.expectRevert(
            abi.encodeWithSelector(
                DeployTechtreeGraphRegistryV1BaseSepolia.RolesNotDistinct.selector,
                address(1),
                address(1),
                address(3)
            )
        );
        harness.requireDistinctRoles(address(1), address(1), address(3));
        vm.expectRevert(
            abi.encodeWithSelector(
                DeployTechtreeGraphRegistryV1BaseSepolia.RolesNotDistinct.selector,
                address(1),
                address(2),
                address(1)
            )
        );
        harness.requireDistinctRoles(address(1), address(2), address(1));
        vm.expectRevert(
            abi.encodeWithSelector(
                DeployTechtreeGraphRegistryV1BaseSepolia.RolesNotDistinct.selector,
                address(1),
                address(2),
                address(2)
            )
        );
        harness.requireDistinctRoles(address(1), address(2), address(2));
    }

    function testBaseMainnetDeployRequiresThreeDistinctRoles() public {
        BaseMainnetDeployHarness harness = new BaseMainnetDeployHarness();
        harness.requireDistinctRoles(address(1), address(2), address(3));

        vm.expectRevert(
            abi.encodeWithSelector(
                DeployTechtreeGraphRegistryV1BaseMainnet.RolesNotDistinct.selector,
                address(1),
                address(1),
                address(3)
            )
        );
        harness.requireDistinctRoles(address(1), address(1), address(3));
        vm.expectRevert(
            abi.encodeWithSelector(
                DeployTechtreeGraphRegistryV1BaseMainnet.RolesNotDistinct.selector,
                address(1),
                address(2),
                address(1)
            )
        );
        harness.requireDistinctRoles(address(1), address(2), address(1));
        vm.expectRevert(
            abi.encodeWithSelector(
                DeployTechtreeGraphRegistryV1BaseMainnet.RolesNotDistinct.selector,
                address(1),
                address(2),
                address(2)
            )
        );
        harness.requireDistinctRoles(address(1), address(2), address(2));
    }

    function testRegisterAndRetireTree() public {
        vm.expectEmit(true, false, false, true, address(registry));
        emit TreeRegistered(TREE, TechtreeGraphRegistryV1.TreeStatus.ACTIVE);
        _registerTree(TREE);

        TechtreeGraphRegistryV1.TreeRecord memory record = registry.getTree(TREE);
        assertEq(record.treeUid, TREE);
        assertEq(uint8(record.status), uint8(TechtreeGraphRegistryV1.TreeStatus.ACTIVE));

        vm.expectEmit(true, false, false, true, address(registry));
        emit TreeStatusUpdated(
            TREE,
            TechtreeGraphRegistryV1.TreeStatus.ACTIVE,
            TechtreeGraphRegistryV1.TreeStatus.RETIRED
        );
        vm.prank(REGISTRAR);
        registry.retireTree(TREE);
        assertEq(
            uint8(registry.getTree(TREE).status), uint8(TechtreeGraphRegistryV1.TreeStatus.RETIRED)
        );
    }

    function testTreeRevertsAndIdempotency() public {
        vm.expectRevert(TechtreeGraphRegistryV1.ZeroUid.selector);
        vm.prank(REGISTRAR);
        registry.registerTree(bytes32(0));

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.Unauthorized.selector, OTHER)
        );
        vm.prank(OTHER);
        registry.registerTree(TREE);

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordNotFound.selector, TREE)
        );
        registry.getTree(TREE);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordNotFound.selector, TREE)
        );
        vm.prank(REGISTRAR);
        registry.retireTree(TREE);

        _registerTree(TREE);
        vm.recordLogs();
        _registerTree(TREE);
        assertEq(vm.getRecordedLogs().length, 0);

        vm.prank(REGISTRAR);
        registry.retireTree(TREE);
        vm.recordLogs();
        vm.prank(REGISTRAR);
        registry.retireTree(TREE);
        assertEq(vm.getRecordedLogs().length, 0);
    }

    function testRegisterRootAndParentedNode() public {
        _registerTree(TREE);
        TechtreeGraphRegistryV1.RecordedPublisher memory publisher = _publisher();

        vm.expectEmit(true, true, true, true, address(registry));
        emit NodeRegistered(
            ROOT,
            REVISION,
            TREE,
            bytes32(0),
            KIND,
            publisher.registry,
            publisher.agentId,
            publisher.tokenId,
            TechtreeGraphRegistryV1.NodeStatus.PUBLISHED,
            bytes32(0)
        );
        _registerNode(ROOT, bytes32(0), publisher);
        _registerNode(CHILD, ROOT, publisher);

        TechtreeGraphRegistryV1.NodeRecord memory root = registry.getNode(ROOT);
        TechtreeGraphRegistryV1.NodeRecord memory child = registry.getNode(CHILD);
        assertEq(root.revisionUid, REVISION);
        assertEq(child.revisionUid, REVISION);
        assertEq(root.parentNodeUid, bytes32(0));
        assertEq(child.parentNodeUid, ROOT);
        assertEq(child.treeUid, TREE);
        assertEq(child.nodeKind, KIND);
        assertEq(child.recordedPublisher.registry, publisher.registry);
        assertEq(child.recordedPublisher.agentId, publisher.agentId);
        assertEq(child.recordedPublisher.tokenId, publisher.tokenId);
    }

    function testNodeAdmissionReverts() public {
        TechtreeGraphRegistryV1.RecordedPublisher memory publisher = _publisher();
        vm.expectRevert(TechtreeGraphRegistryV1.ZeroUid.selector);
        vm.prank(REGISTRAR);
        registry.registerNode(bytes32(0), REVISION, TREE, bytes32(0), KIND, publisher);

        vm.expectRevert(TechtreeGraphRegistryV1.ZeroUid.selector);
        vm.prank(REGISTRAR);
        registry.registerNode(ROOT, bytes32(0), TREE, bytes32(0), KIND, publisher);

        vm.expectRevert(TechtreeGraphRegistryV1.ZeroUid.selector);
        vm.prank(REGISTRAR);
        registry.registerNode(ROOT, REVISION, bytes32(0), bytes32(0), KIND, publisher);

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordNotFound.selector, TREE)
        );
        vm.prank(REGISTRAR);
        registry.registerNode(ROOT, REVISION, TREE, bytes32(0), KIND, publisher);

        _registerTree(TREE);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordNotFound.selector, ROOT)
        );
        vm.prank(REGISTRAR);
        registry.registerNode(CHILD, REVISION, TREE, ROOT, KIND, publisher);

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.Unauthorized.selector, OTHER)
        );
        vm.prank(OTHER);
        registry.registerNode(ROOT, REVISION, TREE, bytes32(0), KIND, publisher);

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordNotFound.selector, ROOT)
        );
        registry.getNode(ROOT);
    }

    function testNodeIdempotencyAndConflicts() public {
        _registerTree(TREE);
        TechtreeGraphRegistryV1.RecordedPublisher memory publisher = _publisher();
        _registerNode(ROOT, bytes32(0), publisher);

        vm.recordLogs();
        _registerNode(ROOT, bytes32(0), publisher);
        assertEq(vm.getRecordedLogs().length, 0);

        _expectNodeConflict(ROOT, REVISION, TREE, bytes32(0), bytes32(uint256(12)), publisher);
        _expectNodeConflict(
            ROOT, REVISION, TREE, bytes32(0), KIND, _publisherWith(address(9), publisher.agentId, 7)
        );
        _expectNodeConflict(
            ROOT,
            REVISION,
            TREE,
            bytes32(0),
            KIND,
            _publisherWith(publisher.registry, bytes32(uint256(13)), 7)
        );
        _expectNodeConflict(
            ROOT,
            REVISION,
            TREE,
            bytes32(0),
            KIND,
            _publisherWith(publisher.registry, publisher.agentId, 8)
        );

        _expectNodeConflict(ROOT, NEXT_REVISION, TREE, bytes32(0), KIND, publisher);

        bytes32 otherTree = bytes32(uint256(88));
        _registerTree(otherTree);
        _expectNodeConflict(ROOT, REVISION, otherTree, bytes32(0), KIND, publisher);
        _registerNode(CHILD, bytes32(0), publisher);
        _expectNodeConflict(ROOT, REVISION, TREE, CHILD, KIND, publisher);
    }

    function testRegisterNodeRevision() public {
        _registerTree(TREE);
        _registerNode(ROOT, bytes32(0), _publisher());

        vm.expectEmit(true, false, false, true, address(registry));
        emit NodeRevisionRegistered(ROOT, REVISION, NEXT_REVISION);
        vm.prank(REGISTRAR);
        registry.registerNodeRevision(ROOT, NEXT_REVISION);
        assertEq(registry.getNode(ROOT).revisionUid, NEXT_REVISION);

        vm.recordLogs();
        vm.prank(REGISTRAR);
        registry.registerNodeRevision(ROOT, NEXT_REVISION);
        assertEq(vm.getRecordedLogs().length, 0);
    }

    function testRegisterNodeRevisionReverts() public {
        vm.expectRevert(TechtreeGraphRegistryV1.ZeroUid.selector);
        vm.prank(REGISTRAR);
        registry.registerNodeRevision(ROOT, bytes32(0));

        vm.expectRevert(TechtreeGraphRegistryV1.ZeroUid.selector);
        vm.prank(REGISTRAR);
        registry.registerNodeRevision(bytes32(0), NEXT_REVISION);

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordNotFound.selector, ROOT)
        );
        vm.prank(REGISTRAR);
        registry.registerNodeRevision(ROOT, NEXT_REVISION);

        _registerTree(TREE);
        _registerNode(ROOT, bytes32(0), _publisher());
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.Unauthorized.selector, OTHER)
        );
        vm.prank(OTHER);
        registry.registerNodeRevision(ROOT, NEXT_REVISION);

        vm.prank(REGISTRAR);
        registry.retractNode(ROOT);
        vm.expectRevert(
            abi.encodeWithSelector(
                TechtreeGraphRegistryV1.RevisionUpdateNotAllowed.selector,
                ROOT,
                TechtreeGraphRegistryV1.NodeStatus.RETRACTED
            )
        );
        vm.prank(REGISTRAR);
        registry.registerNodeRevision(ROOT, NEXT_REVISION);
    }

    function testSupersedeNode() public {
        _seedNodes();
        TechtreeGraphRegistryV1.RecordedPublisher memory publisher = _publisher();
        vm.prank(REGISTRAR);
        registry.registerNodeRevision(ROOT, NEXT_REVISION);
        vm.expectEmit(true, true, true, true, address(registry));
        emit NodeStatusUpdated(
            ROOT,
            NEXT_REVISION,
            TREE,
            bytes32(0),
            KIND,
            publisher.registry,
            publisher.agentId,
            publisher.tokenId,
            TechtreeGraphRegistryV1.NodeStatus.PUBLISHED,
            TechtreeGraphRegistryV1.NodeStatus.SUPERSEDED,
            CHILD
        );
        vm.prank(REGISTRAR);
        registry.supersedeNode(ROOT, CHILD);

        TechtreeGraphRegistryV1.NodeRecord memory record = registry.getNode(ROOT);
        assertEq(uint8(record.status), uint8(TechtreeGraphRegistryV1.NodeStatus.SUPERSEDED));
        assertEq(record.supersededBy, CHILD);

        vm.recordLogs();
        vm.prank(REGISTRAR);
        registry.registerNode(ROOT, NEXT_REVISION, TREE, bytes32(0), KIND, publisher);
        assertEq(vm.getRecordedLogs().length, 0);
    }

    function testSupersedeNodeReverts() public {
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordNotFound.selector, ROOT)
        );
        vm.prank(REGISTRAR);
        registry.supersedeNode(ROOT, CHILD);

        _seedNodes();
        _registerNode(THIRD, CHILD, _publisher());
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.InvalidSupersededBy.selector, bytes32(0))
        );
        vm.prank(REGISTRAR);
        registry.supersedeNode(ROOT, bytes32(0));

        bytes32 missing = bytes32(uint256(99));
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.InvalidSupersededBy.selector, missing)
        );
        vm.prank(REGISTRAR);
        registry.supersedeNode(ROOT, missing);

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.InvalidSupersededBy.selector, ROOT)
        );
        vm.prank(REGISTRAR);
        registry.supersedeNode(ROOT, ROOT);

        vm.prank(REGISTRAR);
        registry.supersedeNode(ROOT, CHILD);
        vm.recordLogs();
        vm.prank(REGISTRAR);
        registry.supersedeNode(ROOT, CHILD);
        assertEq(vm.getRecordedLogs().length, 0);

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordConflict.selector, ROOT)
        );
        vm.prank(REGISTRAR);
        registry.supersedeNode(ROOT, THIRD);
    }

    function testRejectsRetractedAndSupersededSuccessors() public {
        _seedThreeNodes();

        vm.prank(REGISTRAR);
        registry.retractNode(CHILD);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.InvalidSupersededBy.selector, CHILD)
        );
        vm.prank(REGISTRAR);
        registry.supersedeNode(ROOT, CHILD);

        vm.prank(REGISTRAR);
        registry.supersedeNode(THIRD, ROOT);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.InvalidSupersededBy.selector, THIRD)
        );
        vm.prank(REGISTRAR);
        registry.supersedeNode(ROOT, THIRD);

        vm.expectRevert(
            abi.encodeWithSelector(
                TechtreeGraphRegistryV1.RevisionUpdateNotAllowed.selector,
                THIRD,
                TechtreeGraphRegistryV1.NodeStatus.SUPERSEDED
            )
        );
        vm.prank(REGISTRAR);
        registry.registerNodeRevision(THIRD, NEXT_REVISION);
    }

    function testRejectsTwoNodeSupersessionCycle() public {
        _seedNodes();
        vm.prank(REGISTRAR);
        registry.supersedeNode(ROOT, CHILD);

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.InvalidSupersededBy.selector, ROOT)
        );
        vm.prank(REGISTRAR);
        registry.supersedeNode(CHILD, ROOT);
    }

    function testRejectsThreeNodeSupersessionCycle() public {
        _seedThreeNodes();
        vm.startPrank(REGISTRAR);
        registry.supersedeNode(ROOT, CHILD);
        registry.supersedeNode(CHILD, THIRD);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.InvalidSupersededBy.selector, ROOT)
        );
        registry.supersedeNode(THIRD, ROOT);
        vm.stopPrank();
    }

    function testRejectsTransitionsFromDifferentTerminalState() public {
        _seedNodes();
        vm.prank(REGISTRAR);
        registry.supersedeNode(ROOT, CHILD);
        vm.expectRevert(
            abi.encodeWithSelector(
                TechtreeGraphRegistryV1.InvalidStatusTransition.selector,
                uint8(TechtreeGraphRegistryV1.NodeStatus.SUPERSEDED),
                uint8(TechtreeGraphRegistryV1.NodeStatus.RETRACTED)
            )
        );
        vm.prank(REGISTRAR);
        registry.retractNode(ROOT);

        vm.prank(REGISTRAR);
        registry.retractNode(CHILD);
        vm.expectRevert(
            abi.encodeWithSelector(
                TechtreeGraphRegistryV1.InvalidStatusTransition.selector,
                uint8(TechtreeGraphRegistryV1.NodeStatus.RETRACTED),
                uint8(TechtreeGraphRegistryV1.NodeStatus.SUPERSEDED)
            )
        );
        vm.prank(REGISTRAR);
        registry.supersedeNode(CHILD, THIRD);
    }

    function testRetractNodeAndReverts() public {
        _registerTree(TREE);
        TechtreeGraphRegistryV1.RecordedPublisher memory publisher = _publisher();
        _registerNode(ROOT, bytes32(0), publisher);
        vm.expectEmit(true, true, true, true, address(registry));
        emit NodeStatusUpdated(
            ROOT,
            REVISION,
            TREE,
            bytes32(0),
            KIND,
            publisher.registry,
            publisher.agentId,
            publisher.tokenId,
            TechtreeGraphRegistryV1.NodeStatus.PUBLISHED,
            TechtreeGraphRegistryV1.NodeStatus.RETRACTED,
            bytes32(0)
        );
        vm.prank(REGISTRAR);
        registry.retractNode(ROOT);
        assertEq(
            uint8(registry.getNode(ROOT).status),
            uint8(TechtreeGraphRegistryV1.NodeStatus.RETRACTED)
        );

        vm.recordLogs();
        vm.prank(REGISTRAR);
        registry.retractNode(ROOT);
        assertEq(vm.getRecordedLogs().length, 0);

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordNotFound.selector, CHILD)
        );
        vm.prank(REGISTRAR);
        registry.retractNode(CHILD);

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.Unauthorized.selector, OTHER)
        );
        vm.prank(OTHER);
        registry.retractNode(ROOT);
    }

    function testAllSixEdgeKinds() public {
        _seedNodes();
        for (uint8 i; i < 6; ++i) {
            bytes32 edgeUid = bytes32(uint256(100 + i));
            TechtreeGraphRegistryV1.EdgeKind kind = TechtreeGraphRegistryV1.EdgeKind(i);
            vm.expectEmit(true, true, true, true, address(registry));
            emit EdgeRegistered(
                edgeUid, ROOT, CHILD, kind, TechtreeGraphRegistryV1.EdgeStatus.ACTIVE
            );
            vm.prank(REGISTRAR);
            registry.registerEdge(edgeUid, ROOT, CHILD, kind);
            TechtreeGraphRegistryV1.EdgeRecord memory record = registry.getEdge(edgeUid);
            assertEq(uint8(record.kind), i);
            assertEq(uint8(record.status), uint8(TechtreeGraphRegistryV1.EdgeStatus.ACTIVE));
        }
    }

    function testEdgeAdmissionIdempotencyAndConflicts() public {
        _seedNodes();
        vm.expectRevert(TechtreeGraphRegistryV1.ZeroUid.selector);
        vm.prank(REGISTRAR);
        registry.registerEdge(
            bytes32(0), ROOT, CHILD, TechtreeGraphRegistryV1.EdgeKind.DERIVED_FROM
        );

        vm.expectRevert(TechtreeGraphRegistryV1.ZeroUid.selector);
        vm.prank(REGISTRAR);
        registry.registerEdge(
            EDGE, bytes32(0), CHILD, TechtreeGraphRegistryV1.EdgeKind.DERIVED_FROM
        );

        vm.expectRevert(TechtreeGraphRegistryV1.ZeroUid.selector);
        vm.prank(REGISTRAR);
        registry.registerEdge(EDGE, ROOT, bytes32(0), TechtreeGraphRegistryV1.EdgeKind.DERIVED_FROM);

        bytes32 missing = bytes32(uint256(99));
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordNotFound.selector, missing)
        );
        vm.prank(REGISTRAR);
        registry.registerEdge(EDGE, missing, CHILD, TechtreeGraphRegistryV1.EdgeKind.DERIVED_FROM);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordNotFound.selector, missing)
        );
        vm.prank(REGISTRAR);
        registry.registerEdge(EDGE, ROOT, missing, TechtreeGraphRegistryV1.EdgeKind.DERIVED_FROM);

        _registerEdge(EDGE);
        vm.recordLogs();
        _registerEdge(EDGE);
        assertEq(vm.getRecordedLogs().length, 0);

        _expectEdgeConflict(EDGE, CHILD, ROOT, TechtreeGraphRegistryV1.EdgeKind.DERIVED_FROM);
        _expectEdgeConflict(EDGE, ROOT, CHILD, TechtreeGraphRegistryV1.EdgeKind.SUPPORTS);

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.Unauthorized.selector, OTHER)
        );
        vm.prank(OTHER);
        registry.registerEdge(
            bytes32(uint256(77)), ROOT, CHILD, TechtreeGraphRegistryV1.EdgeKind.SUPPORTS
        );
    }

    function testRetractEdgeAndReverts() public {
        _seedNodes();
        _registerEdge(EDGE);
        vm.expectEmit(true, true, true, true, address(registry));
        emit EdgeStatusUpdated(
            EDGE,
            ROOT,
            CHILD,
            TechtreeGraphRegistryV1.EdgeKind.DERIVED_FROM,
            TechtreeGraphRegistryV1.EdgeStatus.ACTIVE,
            TechtreeGraphRegistryV1.EdgeStatus.RETRACTED
        );
        vm.prank(REGISTRAR);
        registry.retractEdge(EDGE);
        assertEq(
            uint8(registry.getEdge(EDGE).status),
            uint8(TechtreeGraphRegistryV1.EdgeStatus.RETRACTED)
        );

        vm.recordLogs();
        vm.prank(REGISTRAR);
        registry.retractEdge(EDGE);
        assertEq(vm.getRecordedLogs().length, 0);

        bytes32 missing = bytes32(uint256(55));
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordNotFound.selector, missing)
        );
        vm.prank(REGISTRAR);
        registry.retractEdge(missing);

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.Unauthorized.selector, OTHER)
        );
        vm.prank(OTHER);
        registry.retractEdge(EDGE);
    }

    function testNodeBatchSupportsEarlierParentAndIsAtomic() public {
        _registerTree(TREE);
        TechtreeGraphRegistryV1.NodeInput[] memory inputs =
            new TechtreeGraphRegistryV1.NodeInput[](2);
        inputs[0] = _nodeInput(ROOT, bytes32(0));
        inputs[1] = _nodeInput(CHILD, ROOT);
        vm.prank(REGISTRAR);
        registry.registerNodes(inputs);
        assertEq(registry.getNode(CHILD).parentNodeUid, ROOT);

        bytes32 fresh = bytes32(uint256(71));
        TechtreeGraphRegistryV1.NodeInput[] memory invalidInputs =
            new TechtreeGraphRegistryV1.NodeInput[](2);
        invalidInputs[0] = _nodeInput(fresh, bytes32(0));
        invalidInputs[1] = _nodeInput(bytes32(uint256(72)), bytes32(uint256(999)));
        vm.expectRevert(
            abi.encodeWithSelector(
                TechtreeGraphRegistryV1.RecordNotFound.selector, bytes32(uint256(999))
            )
        );
        vm.prank(REGISTRAR);
        registry.registerNodes(invalidInputs);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordNotFound.selector, fresh)
        );
        registry.getNode(fresh);
    }

    function testNodeBatchBoundsAndRole() public {
        TechtreeGraphRegistryV1.NodeInput[] memory empty =
            new TechtreeGraphRegistryV1.NodeInput[](0);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.InvalidBatchLength.selector, 0)
        );
        vm.prank(REGISTRAR);
        registry.registerNodes(empty);

        TechtreeGraphRegistryV1.NodeInput[] memory tooMany =
            new TechtreeGraphRegistryV1.NodeInput[](101);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.InvalidBatchLength.selector, 101)
        );
        vm.prank(REGISTRAR);
        registry.registerNodes(tooMany);

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.Unauthorized.selector, OTHER)
        );
        vm.prank(OTHER);
        registry.registerNodes(empty);
    }

    function testEdgeBatchAndBounds() public {
        _seedNodes();
        TechtreeGraphRegistryV1.EdgeInput[] memory inputs =
            new TechtreeGraphRegistryV1.EdgeInput[](2);
        inputs[0] = _edgeInput(EDGE, TechtreeGraphRegistryV1.EdgeKind.SUPPORTS);
        inputs[1] = _edgeInput(bytes32(uint256(5)), TechtreeGraphRegistryV1.EdgeKind.CONTRADICTS);
        vm.prank(REGISTRAR);
        registry.registerEdges(inputs);
        assertEq(
            uint8(registry.getEdge(EDGE).kind), uint8(TechtreeGraphRegistryV1.EdgeKind.SUPPORTS)
        );

        TechtreeGraphRegistryV1.EdgeInput[] memory empty =
            new TechtreeGraphRegistryV1.EdgeInput[](0);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.InvalidBatchLength.selector, 0)
        );
        vm.prank(REGISTRAR);
        registry.registerEdges(empty);

        TechtreeGraphRegistryV1.EdgeInput[] memory tooMany =
            new TechtreeGraphRegistryV1.EdgeInput[](101);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.InvalidBatchLength.selector, 101)
        );
        vm.prank(REGISTRAR);
        registry.registerEdges(tooMany);

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.Unauthorized.selector, OTHER)
        );
        vm.prank(OTHER);
        registry.registerEdges(empty);
    }

    function testEdgeBatchIsAtomic() public {
        _seedNodes();
        bytes32 fresh = bytes32(uint256(70));
        bytes32 missing = bytes32(uint256(999));
        TechtreeGraphRegistryV1.EdgeInput[] memory inputs =
            new TechtreeGraphRegistryV1.EdgeInput[](2);
        inputs[0] = _edgeInput(fresh, TechtreeGraphRegistryV1.EdgeKind.SUPPORTS);
        inputs[1] = TechtreeGraphRegistryV1.EdgeInput({
            edgeUid: bytes32(uint256(71)),
            fromNodeUid: ROOT,
            toNodeUid: missing,
            kind: TechtreeGraphRegistryV1.EdgeKind.SUPPORTS
        });
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordNotFound.selector, missing)
        );
        vm.prank(REGISTRAR);
        registry.registerEdges(inputs);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordNotFound.selector, fresh)
        );
        registry.getEdge(fresh);
    }

    function testContractRejectsEther() public {
        vm.deal(OTHER, 1 ether);
        vm.prank(OTHER);
        (bool success,) = address(registry).call{value: 1 ether}("");
        assertFalse(success);
        assertEq(address(registry).balance, 0);
    }

    function testStatusWritesEnforceRegistrarRole() public {
        _seedNodes();
        _registerEdge(EDGE);

        vm.startPrank(OTHER);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.Unauthorized.selector, OTHER)
        );
        registry.retireTree(TREE);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.Unauthorized.selector, OTHER)
        );
        registry.supersedeNode(ROOT, CHILD);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.Unauthorized.selector, OTHER)
        );
        registry.registerNodeRevision(ROOT, NEXT_REVISION);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.Unauthorized.selector, OTHER)
        );
        registry.retractNode(ROOT);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.Unauthorized.selector, OTHER)
        );
        registry.retractEdge(EDGE);
        vm.stopPrank();
    }

    function testGasSingleNodeRegistration() public {
        vm.pauseGasMetering();
        _registerTree(TREE);
        TechtreeGraphRegistryV1.RecordedPublisher memory publisher = _publisher();
        vm.resumeGasMetering();
        vm.prank(REGISTRAR);
        registry.registerNode(ROOT, REVISION, TREE, bytes32(0), KIND, publisher);
    }

    function testGasBatchNodeRegistration() public {
        vm.pauseGasMetering();
        _registerTree(TREE);
        TechtreeGraphRegistryV1.NodeInput[] memory inputs =
            new TechtreeGraphRegistryV1.NodeInput[](10);
        for (uint256 i; i < inputs.length; ++i) {
            inputs[i] = _nodeInput(bytes32(uint256(1000 + i)), bytes32(0));
        }
        vm.resumeGasMetering();
        vm.prank(REGISTRAR);
        registry.registerNodes(inputs);
    }

    function testGasSingleEdgeRegistration() public {
        vm.pauseGasMetering();
        _seedNodes();
        vm.resumeGasMetering();
        _registerEdge(EDGE);
    }

    function testGasBatchEdgeRegistration() public {
        vm.pauseGasMetering();
        _seedNodes();
        TechtreeGraphRegistryV1.EdgeInput[] memory inputs =
            new TechtreeGraphRegistryV1.EdgeInput[](10);
        for (uint256 i; i < inputs.length; ++i) {
            inputs[i] =
                _edgeInput(bytes32(uint256(2000 + i)), TechtreeGraphRegistryV1.EdgeKind.REPRODUCES);
        }
        vm.resumeGasMetering();
        vm.prank(REGISTRAR);
        registry.registerEdges(inputs);
    }

    function _registerTree(bytes32 treeUid) internal {
        vm.prank(REGISTRAR);
        registry.registerTree(treeUid);
    }

    function _registerNode(
        bytes32 nodeUid,
        bytes32 parentNodeUid,
        TechtreeGraphRegistryV1.RecordedPublisher memory publisher
    ) internal {
        vm.prank(REGISTRAR);
        registry.registerNode(nodeUid, REVISION, TREE, parentNodeUid, KIND, publisher);
    }

    function _registerEdge(bytes32 edgeUid) internal {
        vm.prank(REGISTRAR);
        registry.registerEdge(edgeUid, ROOT, CHILD, TechtreeGraphRegistryV1.EdgeKind.DERIVED_FROM);
    }

    function _seedNodes() internal {
        _registerTree(TREE);
        TechtreeGraphRegistryV1.RecordedPublisher memory publisher = _publisher();
        _registerNode(ROOT, bytes32(0), publisher);
        _registerNode(CHILD, ROOT, publisher);
    }

    function _seedThreeNodes() internal {
        _seedNodes();
        _registerNode(THIRD, CHILD, _publisher());
    }

    function _publisher() internal pure returns (TechtreeGraphRegistryV1.RecordedPublisher memory) {
        return _publisherWith(address(0x1234), bytes32(uint256(14)), 7);
    }

    function _publisherWith(address publisherRegistry, bytes32 agentId, uint256 tokenId)
        internal
        pure
        returns (TechtreeGraphRegistryV1.RecordedPublisher memory)
    {
        return TechtreeGraphRegistryV1.RecordedPublisher({
            registry: publisherRegistry, agentId: agentId, tokenId: tokenId
        });
    }

    function _nodeInput(bytes32 nodeUid, bytes32 parentNodeUid)
        internal
        pure
        returns (TechtreeGraphRegistryV1.NodeInput memory)
    {
        return TechtreeGraphRegistryV1.NodeInput({
            nodeUid: nodeUid,
            revisionUid: REVISION,
            treeUid: TREE,
            parentNodeUid: parentNodeUid,
            nodeKind: KIND,
            recordedPublisher: TechtreeGraphRegistryV1.RecordedPublisher({
                registry: address(0x1234), agentId: bytes32(uint256(14)), tokenId: 7
            })
        });
    }

    function _edgeInput(bytes32 edgeUid, TechtreeGraphRegistryV1.EdgeKind kind)
        internal
        pure
        returns (TechtreeGraphRegistryV1.EdgeInput memory)
    {
        return TechtreeGraphRegistryV1.EdgeInput({
            edgeUid: edgeUid, fromNodeUid: ROOT, toNodeUid: CHILD, kind: kind
        });
    }

    function _expectNodeConflict(
        bytes32 nodeUid,
        bytes32 revisionUid,
        bytes32 treeUid,
        bytes32 parentNodeUid,
        bytes32 nodeKind,
        TechtreeGraphRegistryV1.RecordedPublisher memory publisher
    ) internal {
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordConflict.selector, nodeUid)
        );
        vm.prank(REGISTRAR);
        registry.registerNode(nodeUid, revisionUid, treeUid, parentNodeUid, nodeKind, publisher);
    }

    function _expectEdgeConflict(
        bytes32 edgeUid,
        bytes32 fromNodeUid,
        bytes32 toNodeUid,
        TechtreeGraphRegistryV1.EdgeKind kind
    ) internal {
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordConflict.selector, edgeUid)
        );
        vm.prank(REGISTRAR);
        registry.registerEdge(edgeUid, fromNodeUid, toNodeUid, kind);
    }
}
