import copy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from train_identifier_pilot import pilot_gate


def scores(identifier=.1,overall=.7,normalized=.9,clean=.98):
    return dict(raw_augmented=dict(identifier_accuracy=identifier,accuracy=overall),
        normalized_augmented=dict(accuracy=normalized),normalized_clean=dict(accuracy=clean))


def test_expansion_requires_identifier_improvement_and_regression_checks():
    baseline=scores()
    assert pilot_gate(baseline,scores(identifier=.8,overall=.85))['passed']
    assert not pilot_gate(baseline,scores(identifier=.15,overall=.8))['passed']
    assert not pilot_gate(baseline,scores(identifier=.8,overall=.6))['passed']
    assert not pilot_gate(baseline,scores(identifier=.8,overall=.8,normalized=.85))['passed']
    assert not pilot_gate(baseline,scores(identifier=.8,overall=.8,clean=.9))['passed']
