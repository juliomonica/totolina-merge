"""Closed schemas, bounded metadata and malformed-wire validation."""
from copy import deepcopy
import json
import unittest

from pydantic import TypeAdapter

from modules.godot.protocol import (BridgeError, EditorStateResult, MAX_PAYLOAD_BYTES,
                                   PingResult, RigLabResult, SceneInspectionResult, WRITE_OPERATION, decode, encode,
                                   envelope, proof, validate_authenticate, validate_hello,
                                   validate_response, validate_result, validate_scene)
from tests.fake_godot_client import (NO_SCENE, ROOT_NODE, SAVED_SCENE, UNNAMED_SCENE,
                                     disposable_credential, ping, result_for)


class GodotProtocolTests(unittest.TestCase):
    def setUp(self):
        self.credential = disposable_credential()
        self.inspection = result_for("godot_inspect_scene", self.credential, SAVED_SCENE, [ROOT_NODE], [])

    def invalid(self, value, operation="godot_inspect_scene", code="INVALID_MESSAGE"):
        with self.assertRaises(BridgeError) as caught:
            validate_result(operation, value)
        self.assertEqual(caught.exception.code, code)

    def test_all_success_and_failure_contracts_validate(self):
        for operation, result_type in (("godot_ping", PingResult),
                                       ("godot_get_editor_state", EditorStateResult),
                                       ("godot_inspect_scene", SceneInspectionResult),
                                       (WRITE_OPERATION, RigLabResult)):
            with self.subTest(operation=operation):
                data = result_for(operation, self.credential, NO_SCENE, [], [])
                validate_result(operation, data)
                TypeAdapter(result_type).validate_python(envelope(data, elapsed_ms=1.0))
                TypeAdapter(result_type).validate_python(envelope(error=BridgeError("DISCONNECTED")))

    def test_schema_rejects_unknown_nested_fields(self):
        value = envelope(self.inspection, elapsed_ms=1.0)
        value["result"]["nodes"][0]["secret_property"] = "never returned"
        with self.assertRaises(ValueError):
            TypeAdapter(SceneInspectionResult).validate_python(value)

    def test_no_scene_and_unnamed_state(self):
        validate_scene(NO_SCENE)
        validate_scene(UNNAMED_SCENE)
        data = result_for("godot_inspect_scene", self.credential, NO_SCENE, [], [])
        validate_result("godot_inspect_scene", data)
        data["nodes"] = [deepcopy(ROOT_NODE)]
        self.invalid(data)

    def test_saved_dirty_state_consistency(self):
        scene = deepcopy(SAVED_SCENE)
        scene["save_state"], scene["dirty_changes"] = "saved_dirty", True
        validate_scene(scene)
        scene["dirty_changes"] = False
        with self.assertRaises(BridgeError):
            validate_scene(scene)

    def test_unnamed_dirty_state_never_guesses(self):
        scene = deepcopy(UNNAMED_SCENE)
        scene["dirty_changes"] = False
        with self.assertRaises(BridgeError):
            validate_scene(scene)

    def test_rejects_duplicate_json_fields_constants_and_binary(self):
        for raw in ('{"protocol_version":1,"protocol_version":1}',
                    '{"protocol_version":1,"x":NaN}', '{"protocol_version":1,"x":Infinity}',
                    b'{"protocol_version":1}', '[]', '{', '{"protocol_version":true}'):
            with self.subTest(raw_type=type(raw).__name__):
                with self.assertRaises(BridgeError):
                    decode(raw)

    def test_frame_limit_counts_utf8_encoded_bytes(self):
        raw = '{"protocol_version":1,"x":"' + "猫" * MAX_PAYLOAD_BYTES + '"}'
        with self.assertRaises(BridgeError) as caught:
            decode(raw)
        self.assertEqual(caught.exception.code, "RESPONSE_TOO_LARGE")
        with self.assertRaises(BridgeError):
            encode({"protocol_version": 1, "x": "a" * MAX_PAYLOAD_BYTES})

    def test_string_limit_counts_utf8_bytes(self):
        data = ping(self.credential)
        data["project_name"] = "猫" * 2000
        self.invalid(data, "godot_ping")

    def test_unknown_metadata_and_operation_rejected(self):
        self.inspection["arbitrary_resource"] = {}
        self.invalid(self.inspection)
        self.invalid({}, "godot_save_scene", "UNSUPPORTED_OPERATION")

    def test_unknown_host_and_false_read_only_rejected(self):
        data = ping(self.credential)
        data["godot_version"] = "4.6.0"
        self.invalid(data, "godot_ping", "UNSUPPORTED_HOST")
        data["godot_version"], data["read_only"] = "4.7.2", False
        self.invalid(data, "godot_ping")

    def test_2000_nodes_accepted_2001_rejected(self):
        root = deepcopy(ROOT_NODE)
        root["child_count"] = 1999
        self.inspection["nodes"] = [root] + [dict(ROOT_NODE, path=f"Child{i}", parent_path=".") for i in range(1999)]
        validate_result("godot_inspect_scene", self.inspection)
        self.inspection["nodes"].append(dict(ROOT_NODE, path="Extra", parent_path="."))
        self.invalid(self.inspection)

    def test_depth_64_accepted_65_rejected(self):
        self.inspection["nodes"] = []
        for depth in range(65):
            path = "/".join(["Child"] * depth) if depth else "."
            parent = None if depth == 0 else "/".join(["Child"] * (depth - 1)) if depth > 1 else "."
            self.inspection["nodes"].append(dict(ROOT_NODE, path=path, parent_path=parent,
                                                child_count=1 if depth < 64 else 0))
        validate_result("godot_inspect_scene", self.inspection)
        self.inspection["nodes"][-1]["child_count"] = 1
        self.inspection["nodes"].append(dict(ROOT_NODE, path="/".join(["Child"] * 65),
                                            parent_path="/".join(["Child"] * 64)))
        self.invalid(self.inspection)

    def test_paths_parent_order_duplicate_and_child_count(self):
        for changes in ({"path": "../outside"}, {"path": "res://outside"}, {"parent_path": "."},
                        {"child_count": 1}, {"child_count": True}, {"type": "AnimationPlayer"}):
            with self.subTest(changes=changes):
                data = deepcopy(self.inspection)
                data["nodes"][0].update(changes)
                self.invalid(data)
        self.inspection["nodes"].append(deepcopy(ROOT_NODE))
        self.invalid(self.inspection)

    def test_128_selection_limit_and_explicit_truncation(self):
        selection = [{"path": f"Child{i}", "type": "Node"} for i in range(129)]
        data = result_for("godot_get_editor_state", self.credential, SAVED_SCENE, [], selection)
        validate_result("godot_get_editor_state", data)
        self.assertTrue(data["selected_nodes"]["truncated"])
        data["selected_nodes"]["truncated"] = False
        self.invalid(data, "godot_get_editor_state")

    def test_selection_without_scene_rejected(self):
        data = result_for("godot_get_editor_state", self.credential, NO_SCENE, [], [{"path": ".", "type": "Node"}])
        self.invalid(data, "godot_get_editor_state")

    def test_128_player_names_or_explicit_omission(self):
        player = dict(ROOT_NODE, type="AnimationPlayer", kind="animation_player",
                      animations={"count": 128, "names": [f"anim{i}" for i in range(128)], "omitted_reason": None})
        self.inspection["nodes"] = [player]
        validate_result("godot_inspect_scene", self.inspection)
        player["animations"] = {"count": 129, "names": None, "omitted_reason": "limit"}
        validate_result("godot_inspect_scene", self.inspection)
        player["animations"] = {"count": 1, "names": None, "omitted_reason": "limit"}
        self.invalid(self.inspection)

    def test_512_overall_names_and_explicit_omission(self):
        root = dict(ROOT_NODE, child_count=5)
        players = [dict(ROOT_NODE, path=f"Player{i}", parent_path=".", type="AnimationPlayer", kind="animation_player",
                        animations={"count": 128, "names": [f"anim{j}" for j in range(128)], "omitted_reason": None})
                   for i in range(4)]
        players.append(dict(ROOT_NODE, path="Player4", parent_path=".", type="AnimationPlayer", kind="animation_player",
                            animations={"count": 1, "names": None, "omitted_reason": "limit"}))
        self.inspection["nodes"] = [root] + players
        validate_result("godot_inspect_scene", self.inspection)
        players[-1]["animations"] = {"count": 1, "names": ["overflow"], "omitted_reason": None}
        self.invalid(self.inspection)

    def test_animation_tracks_key_values_and_duplicate_names_rejected(self):
        player = dict(ROOT_NODE, type="AnimationPlayer", kind="animation_player",
                      animations={"count": 1, "names": ["idle"], "omitted_reason": None, "tracks": []})
        self.inspection["nodes"] = [player]
        self.invalid(self.inspection)
        player["animations"] = {"count": 2, "names": ["idle", "idle"], "omitted_reason": None}
        self.invalid(self.inspection)

    def test_response_closed_fields_and_failure_contract(self):
        response = {"type": "response", "protocol_version": 1, "id": "a" * 32, "operation": "godot_ping",
                    "ok": True, "result": ping(self.credential), "error": None}
        validate_response(response)
        for field, value in (("id", "not-a-request-id"), ("extra", True), ("ok", 1), ("error", {})):
            with self.subTest(field=field):
                data = dict(response)
                data[field] = value
                with self.assertRaises(BridgeError):
                    validate_response(data)
        response.update(ok=False, result=None, error={"code": "INSPECTION_FAILED", "message": "peer-controlled"})
        validate_response(response)
        response["error"]["arbitrary"] = 1
        with self.assertRaises(BridgeError):
            validate_response(response)

    def test_auth_shapes_are_closed(self):
        hello = {"type": "hello", "protocol_version": 1, "project_id": "a" * 64, "client_nonce": "b" * 64}
        validate_hello(hello)
        validate_authenticate({"type": "authenticate", "protocol_version": 1, "proof": "c" * 64})
        hello["secret"] = "forbidden"
        with self.assertRaises(BridgeError):
            validate_hello(hello)

    def test_role_project_and_nonce_separation(self):
        args = (self.credential.secret, self.credential.project_id, "a" * 64, "b" * 64)
        server = proof(*args, "server")
        self.assertNotEqual(server, proof(*args, "client"))
        self.assertNotEqual(server, proof(args[0], "c" * 64, args[2], args[3], "server"))
        self.assertNotEqual(server, proof(args[0], args[1], "c" * 64, args[3], "server"))
        self.assertNotEqual(server, proof(args[0], args[1], args[2], "c" * 64, "server"))

    def test_envelope_success_requires_finite_timing(self):
        for timing in (None, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                envelope(ping(self.credential), elapsed_ms=timing)


if __name__ == "__main__":
    unittest.main(verbosity=2)
