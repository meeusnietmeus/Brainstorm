from tests.test_node_service import collect


def test_note_title_follows_first_line_of_body(node_service, global_space):
    node = node_service.create(global_space.id, "note", body="\n  First line  \nsecond")
    assert node.title == "First line"
    updated = node_service.update(node.id, body="New start\nmore")
    assert updated.title == "New start"


def test_title_of_other_kinds_is_not_derived(node_service, global_space):
    node = node_service.create(global_space.id, "link", title="https://x.test", body="whatever")
    assert node_service.update(node.id, body="changed").title == "https://x.test"


def test_set_props_merges_and_none_removes(node_service, global_space):
    node = node_service.create(global_space.id, "note", props={"style": "plain", "fontSize": "M"})
    merged = node_service.set_props(node.id, style="card")
    assert merged.props == {"style": "card", "fontSize": "M"}
    assert node_service.set_props(node.id, fontSize=None).props == {"style": "card"}


def test_resize_is_one_write_with_one_signal(node_service, global_space):
    node = node_service.create(global_space.id, "note", x=0, y=0)
    updated = collect(node_service.nodeUpdated)
    result = node_service.resize(node.id, -10, -5, 300, 80, {"fixedHeight": True})
    assert len(updated) == 1
    assert (result.x, result.y, result.w, result.h) == (-10, -5, 300, 80)
    assert result.props == {"fixedHeight": True}


def make_stack(node_service, space_id, count=3):
    return [node_service.create(space_id, "note", x=i, y=i) for i in range(count)]


def order(node_service, space_id):
    return [n.id for n in sorted(node_service.list(space_id), key=lambda n: n.z)]


def test_shift_z_moves_one_step_and_clamps(node_service, global_space):
    a, b, c = make_stack(node_service, global_space.id)
    node_service.shift_z(a.id, 1)
    assert order(node_service, global_space.id) == [b.id, a.id, c.id]
    node_service.shift_z(a.id, 1)
    assert order(node_service, global_space.id) == [b.id, c.id, a.id]
    assert node_service.shift_z(a.id, 1) == []  # already on top
    node_service.shift_z(a.id, -1)
    assert order(node_service, global_space.id) == [b.id, a.id, c.id]


def test_shift_z_works_after_gaps_from_deleted_nodes(node_service, global_space):
    a, b, c = make_stack(node_service, global_space.id)
    node_service.delete(b.id)
    node_service.shift_z(a.id, 1)
    assert order(node_service, global_space.id) == [c.id, a.id]


def test_shift_z_ignores_nodes_not_on_canvas(node_service, global_space):
    a = node_service.create(global_space.id, "note", x=0, y=0)
    hidden = node_service.create(global_space.id, "code_todo")
    b = node_service.create(global_space.id, "note", x=1, y=1)
    node_service.shift_z(a.id, 1)
    zs = {n.id: n.z for n in node_service.list(global_space.id)}
    assert zs[a.id] > zs[b.id]
    assert node_service.shift_z(hidden.id, 1) == []
