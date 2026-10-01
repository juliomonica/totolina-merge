extends SceneTree
## Disposable native fixtures; this script never loads a production scene.

const Inspection = preload("res://addons/lunitora_godot/inspection.gd")
const BridgeClient = preload("res://addons/lunitora_godot/bridge_client.gd")

var _checks := 0
var _failures := 0
var _inspector := Inspection.new()


class GuardedNode extends Node:
	var property_reads := 0
	var script_property: String:
		get:
			property_reads += 1
			return "ARBITRARY_SCRIPT_PROPERTY_VALUE"


func _initialize() -> void:
	call_deferred("_run")


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		push_error("GODOT_MCP_CHECK_FAILED: " + label)


func _run() -> void:
	_no_scene()
	_metadata_and_selection()
	_node_limits()
	_animation_limits()
	_native_metadata_only()
	_string_and_frame_limits()
	_hmac_vector()
	print("GODOT_MCP_INSPECTION_CHECKS=%d FAILURES=%d" % [_checks, _failures])
	quit(1 if _failures else 0)


func _fixture(name_value: String = "Fixture") -> Node:
	var fixture := Node.new()
	fixture.name = name_value
	root.add_child(fixture)
	return fixture


func _no_scene() -> void:
	var empty := _inspector.inspect_scene(null, PackedStringArray(), "session")
	_check(empty.ok and empty.result.nodes.is_empty(), "no scene returns complete empty tree")
	_check(empty.result.scene == {
		"exists": false, "path": null, "root_name": null,
		"has_saved_path": false, "save_state": "no_scene",
		"dirty_changes": null, "dirty_reason": "no_scene",
	}, "no-scene contract")
	var selection: Array[Node] = []
	var state := _inspector.editor_state(null, selection, PackedStringArray(), "session")
	_check(state.ok and state.result.selected_nodes.total_count == 0, "no-scene state excludes selection")
	var ping := _inspector.ping("session")
	_check(ping.ok and ping.result.read_only and ping.result.godot_version.begins_with("4.7.2"), "verified engine ping metadata")
	_check(ping.result.project_path == _inspector.canonical_project_path(), "canonical project path")
	_check(ping.result.size() == 6, "ping has only approved fields")


func _metadata_and_selection() -> void:
	var fixture := _fixture()
	var child := Node2D.new()
	child.name = "Child"
	fixture.add_child(child)
	var nested := Node.new()
	nested.name = "InstanceDescendant"
	child.add_child(nested)
	var internal := Node.new()
	internal.name = "Internal"
	fixture.add_child(internal, false, Node.INTERNAL_MODE_BACK)
	var selected: Array[Node] = [fixture, child, nested, root]
	var state := _inspector.editor_state(fixture, selected, PackedStringArray(), "session")
	_check(state.ok and state.result.scene.save_state == "new_unsaved", "unnamed scene state")
	_check(state.result.scene.dirty_changes == null and state.result.scene.dirty_reason == "unnamed_scene", "unnamed dirty state remains unknown")
	_check(state.result.selected_nodes.total_count == 3, "selection excludes nodes outside scene")
	_check(state.result.selected_nodes.nodes[0].path == ".", "selected root path is dot")
	fixture.scene_file_path = "res://fixture.tscn"
	_check(_inspector.scene_info(fixture, PackedStringArray()).save_state == "saved_clean", "saved clean state")
	_check(_inspector.scene_info(fixture, PackedStringArray(["res://fixture.tscn"])).save_state == "saved_dirty", "saved dirty state")
	var before := [fixture.name, fixture.scene_file_path, fixture.get_child_count(true), child.get_parent(), child.position]
	var inspected := _inspector.inspect_scene(fixture, PackedStringArray(), "session")
	_check(inspected.ok and inspected.result.nodes.size() == 3, "internal children excluded; instanced descendants included")
	_check(inspected.result.nodes[0].path == "." and inspected.result.nodes[0].parent_path == null, "root metadata contract")
	_check(inspected.result.nodes[1].path == "Child" and inspected.result.nodes[1].type == "Node2D", "native node type and relative path")
	_check(inspected.result.nodes[2].parent_path == "Child", "descendant parent metadata")
	_check(before == [fixture.name, fixture.scene_file_path, fixture.get_child_count(true), child.get_parent(), child.position], "inspection preserves nodes and save path")
	selected.clear()
	for index in range(129):
		var member := Node.new()
		member.name = "S%d" % index
		fixture.add_child(member)
		selected.append(member)
	state = _inspector.editor_state(fixture, selected, PackedStringArray(), "session")
	_check(state.ok and state.result.selected_nodes.nodes.size() == 128, "selection entry limit")
	_check(state.result.selected_nodes.total_count == 129 and state.result.selected_nodes.truncated, "selection truncation is explicit with total")
	_check(selected.size() == 129, "inspection preserves selected-node input")
	fixture.free()


func _node_limits() -> void:
	var fixture := _fixture()
	for index in range(1999):
		var child := Node.new()
		child.name = "N%d" % index
		fixture.add_child(child)
	var inspected := _inspector.inspect_scene(fixture, PackedStringArray(), "session")
	_check(inspected.ok and inspected.result.nodes.size() == 2000, "2000-node boundary accepted")
	fixture.add_child(Node.new())
	inspected = _inspector.inspect_scene(fixture, PackedStringArray(), "session")
	_check(not inspected.ok and inspected.error.code == "SCENE_TOO_LARGE" and inspected.result == null, "2001 nodes returns error without partial tree")
	fixture.free()
	fixture = _fixture()
	var parent := fixture
	for _index in range(64):
		var child := Node.new()
		child.name = "N"
		parent.add_child(child)
		parent = child
	inspected = _inspector.inspect_scene(fixture, PackedStringArray(), "session")
	_check(inspected.ok and inspected.result.nodes.size() == 65, "depth64 boundary accepted")
	parent.add_child(Node.new())
	inspected = _inspector.inspect_scene(fixture, PackedStringArray(), "session")
	_check(not inspected.ok and inspected.error.code == "SCENE_TOO_LARGE", "depth65 returns error")
	fixture.free()


func _player(parent: Node, player_name: String, count: int, library_name: String = "") -> AnimationPlayer:
	var player := AnimationPlayer.new()
	player.name = player_name
	parent.add_child(player)
	var library := AnimationLibrary.new()
	for index in range(count):
		library.add_animation("A%d" % index, Animation.new())
	player.add_animation_library(library_name, library)
	return player


func _animation_limits() -> void:
	var fixture := _fixture()
	var player := _player(fixture, "Player", 128, "library")
	var before := [player.current_animation, player.is_playing(), player.speed_scale]
	var inspected := _inspector.inspect_scene(fixture, PackedStringArray(), "session")
	var metadata: Dictionary = inspected.result.nodes[1].animations
	_check(inspected.ok and metadata.count == 128 and metadata.names.size() == 128, "128 animation names accepted")
	_check(metadata.names.has("library/A0") and metadata.omitted_reason == null, "library-qualified animation names")
	_check(inspected.result.nodes[1].kind == "animation_player", "native AnimationPlayer classification")
	_check(before == [player.current_animation, player.is_playing(), player.speed_scale], "inspection preserves playback state")
	player.get_animation_library("library").add_animation("Extra", Animation.new())
	inspected = _inspector.inspect_scene(fixture, PackedStringArray(), "session")
	metadata = inspected.result.nodes[1].animations
	_check(inspected.ok and metadata.count == 129 and metadata.names == null and metadata.omitted_reason == "limit", "129 names omitted explicitly")
	fixture.free()
	fixture = _fixture()
	for index in range(4):
		_player(fixture, "Player%d" % index, 128)
	_player(fixture, "Overflow", 1)
	_player(fixture, "Empty", 0)
	inspected = _inspector.inspect_scene(fixture, PackedStringArray(), "session")
	var emitted := 0
	for entry in inspected.result.nodes:
		if entry.animations != null and entry.animations.names != null:
			emitted += entry.animations.names.size()
	_check(inspected.ok and emitted == 512, "global512 names accepted")
	_check(inspected.result.nodes[5].animations.names == null and inspected.result.nodes[5].animations.count == 1, "global513 name omitted explicitly")
	_check(inspected.result.nodes[6].animations.names == [] and inspected.result.nodes[6].animations.count == 0, "empty player remains fully reported")
	fixture.free()
	fixture = _fixture()
	player = _player(fixture, "Libraries", 0)
	for index in range(512):
		player.add_animation_library("L%d" % index, AnimationLibrary.new())
	inspected = _inspector.inspect_scene(fixture, PackedStringArray(), "session")
	_check(not inspected.ok and inspected.error.code == "SCENE_TOO_LARGE", "library-enumeration work limit")
	fixture.free()


func _string_and_frame_limits() -> void:
	var fixture := _fixture("N".repeat(4097))
	var inspected := _inspector.inspect_scene(fixture, PackedStringArray(), "session")
	_check(not inspected.ok and inspected.error.code == "RESPONSE_TOO_LARGE", "4097-byte string rejected")
	fixture.free()
	fixture = _fixture()
	for index in range(100):
		var child := Node.new()
		child.name = "N%d_" % index + "x".repeat(3000)
		fixture.add_child(child)
	inspected = _inspector.inspect_scene(fixture, PackedStringArray(), "session")
	_check(not inspected.ok and inspected.error.code == "RESPONSE_TOO_LARGE" and inspected.result == null, "encoded frame over256KiB rejected")
	fixture.free()
	fixture = _fixture()
	var player := _player(fixture, "Player", 0)
	player.get_animation_library("").add_animation("N".repeat(4097), Animation.new())
	inspected = _inspector.inspect_scene(fixture, PackedStringArray(), "session")
	_check(not inspected.ok and inspected.error.code == "RESPONSE_TOO_LARGE", "animation names obey UTF8 byte limit")
	fixture.free()


func _native_metadata_only() -> void:
	var fixture := _fixture()
	var guarded := GuardedNode.new()
	guarded.name = "Guarded"
	fixture.add_child(guarded)
	var player := _player(fixture, "Player", 1)
	var animation := player.get_animation_library("").get_animation("A0")
	animation.add_track(Animation.TYPE_VALUE)
	animation.track_set_path(0, "Guarded:script_property")
	animation.track_insert_key(0, 0.0, "PRIVATE_TRACK_VALUE")
	var inspected := _inspector.inspect_scene(fixture, PackedStringArray(), "session")
	_check(inspected.ok and guarded.property_reads == 0, "arbitrary script getters are never inspected")
	var encoded := JSON.stringify(inspected.result)
	_check(not encoded.contains("ARBITRARY_SCRIPT_PROPERTY_VALUE") and not encoded.contains("PRIVATE_TRACK_VALUE"), "script properties and track values are absent")
	_check(inspected.result.nodes[1].type == "Node" and inspected.result.nodes[1].size() == 6, "scripted node reports native metadata fields only")
	_check(animation.get_track_count() == 1 and animation.track_get_key_value(0, 0) == "PRIVATE_TRACK_VALUE", "inspection preserves animation resource data")
	fixture.free()


func _hmac_vector() -> void:
	var client := BridgeClient.new()
	client._secret = "0b".repeat(20).hex_decode()
	var digest := Crypto.new().hmac_digest(HashingContext.HASH_SHA256, client._secret, "Hi There".to_utf8_buffer())
	_check(digest.hex_encode() == "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7", "Godot HMAC RFC4231 known vector")
	client._secret = "01".repeat(32).hex_decode()
	client._project_id = "02".repeat(32)
	client._client_nonce = "03".repeat(32)
	client._server_nonce = "04".repeat(32)
	var server_proof: PackedByteArray = client._proof("server")
	var client_proof: PackedByteArray = client._proof("client")
	_check(not Crypto.new().constant_time_compare(server_proof, client_proof), "mutual proofs separate roles")
	client._client_nonce = "05".repeat(32)
	_check(not Crypto.new().constant_time_compare(server_proof, client._proof("server")), "proof binds fresh client nonce")
	_check(client._hex("0".repeat(64), 64) and not client._hex("G".repeat(64), 64), "strict lowercase hex validation")
	_check(client._version(1) and not client._version(true) and not client._version(2), "strict protocol version validation")
	_check(client._keys({"type": "ready", "protocol_version": 1}, ["type", "protocol_version"]), "exact wire keys accepted")
	_check(not client._keys({"type": "ready", "protocol_version": 1, "extra": 0}, ["type", "protocol_version"]), "unknown wire fields rejected")
	_check(client._unambiguous_json('{"type":"ready","protocol_version":1}'), "unambiguous JSON accepted")
	_check(not client._unambiguous_json('{"type":"ready","type":"request"}'), "duplicate JSON keys rejected")
	_check(not client._unambiguous_json('{"type":"ready","t\\u0079pe":"request"}'), "escaped duplicate JSON keys rejected")
	_check(not client._unambiguous_json('{"params":{"field":1,"field":2}}'), "nested duplicate JSON keys rejected")
	_check(client._unambiguous_json('{"first":{"field":1},"second":{"field":2}}'), "separate objects may reuse keys")
	_check(client._unambiguous_json('{"text":"{\\\"field\\\":true}","value":[1,2]}'), "string braces and escaped quotes do not affect lexical structure")
	_check(not client._unambiguous_json("[".repeat(17) + "0" + "]".repeat(17)), "excessive JSON nesting rejected before native parsing")
	_check(not client._unambiguous_json('{"text":"' + "x".repeat(4097) + '"}'), "incoming string byte limit enforced")
	client.stop()
	_check(client._secret.is_empty() and client._stage == client.Stage.STOPPED, "shutdown clears authentication state")
