from plural_cognition.boolean_world import And, Const, Ite, Not, Or, Var, canonical_text, normalize


def test_normalization_is_idempotent_and_orders_commutative_children() -> None:
    raw = And((Var("B"), And((Var("A"), Var("B"))), Const(True)))
    normalized = normalize(raw)
    assert normalized == And((Var("A"), Var("B")))
    assert normalize(normalized) == normalized
    assert canonical_text(raw) == "AND(A,B)"


def test_boolean_identities_and_complements() -> None:
    a = Var("A")
    assert normalize(And((a, Const(True)))) == a
    assert normalize(Or((a, Const(False)))) == a
    assert normalize(And((a, Not(a)))) == Const(False)
    assert normalize(Or((a, Not(a)))) == Const(True)
    assert normalize(Not(Not(a))) == a


def test_absorption_and_ite_simplification() -> None:
    a = Var("A")
    b = Var("B")
    assert normalize(Or((a, And((a, b))))) == a
    assert normalize(And((a, Or((a, b))))) == a
    assert normalize(Ite(a, Const(True), Const(False))) == a
    assert normalize(Ite(a, Const(False), Const(True))) == Not(a)
