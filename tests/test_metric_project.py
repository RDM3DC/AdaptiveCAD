import json
from dataclasses import replace

import pytest

from adaptivecad.geom.directional_metric import NormalMetricPatch, balanced_directional_patch
from adaptivecad.metric_project import MetricCurve, MetricHistory, MetricProject, atomic_write


def project():
    return MetricProject(balanced_directional_patch(),
                         (MetricCurve('Native', ((-.4,.1),(0,.5),(.4,.1))),))


def test_roundtrip_keeps_native_coefficients(tmp_path):
    p=project(); text=p.to_json()
    assert MetricProject.from_json(text)==p
    assert 'triangles' not in text and 'vertices' not in text
    path=tmp_path/'a.acmetric.json'; p.save(path)
    assert MetricProject.load(path)==p
    with pytest.raises(FileExistsError): p.save(path)
    assert MetricProject.load(path)==p
    q=replace(p,name='Second'); q.save(path,overwrite=True)
    assert MetricProject.load(path)==q
    assert not list(tmp_path.glob('.*.tmp'))


def test_failed_atomic_write_preserves_existing(tmp_path,monkeypatch):
    path=tmp_path/'existing'; path.write_text('original')
    import adaptivecad.metric_project as module
    def fail(*args): raise OSError('simulated failure')
    monkeypatch.setattr(module.os,'replace',fail)
    with pytest.raises(OSError): atomic_write(path,'replacement',overwrite=True)
    assert path.read_text()=='original'
    assert sorted(x.name for x in tmp_path.iterdir())==['existing']


def test_units_convert_whole_document_and_curvature():
    p=project(); q=p.convert_units('ft_us'); r=q.convert_units('mm')
    assert r.patch.radius==pytest.approx(p.patch.radius)
    for actual, expected in zip(r.curves[0].controls, p.curves[0].controls):
        assert actual == pytest.approx(expected)
    c0=p.patch.gaussian_curvature(.2,.3)
    factor=q.patch.length_scale/p.patch.length_scale
    assert q.patch.gaussian_curvature(.2*factor,.3*factor)*factor**2==pytest.approx(c0)


def test_history_undo_redo_saved_point_and_divergence():
    p=project(); h=MetricHistory(p,limit=2)
    q=replace(p,name='q'); r=replace(p,name='r'); s=replace(p,name='s')
    h.commit(q); h.mark_saved(); h.commit(r)
    assert h.dirty and h.can_undo
    h.undo(); assert not h.dirty and h.can_redo
    h.undo(); h.commit(s); assert not h.can_redo
    assert h.current==s
    with pytest.raises(ValueError): h.commit({})
    assert h.current==s


def test_bounded_history():
    h=MetricHistory(limit=2)
    for i in range(10): h.commit(replace(h.current,name=str(i)))
    assert len(h._states)==3
    h.undo(); h.undo(); h.undo(); assert h.current.name=='7'


def test_split_and_reverse_preserve_curve():
    c=project().curves[0]; a,b=c.split(.37)
    assert a.controls[-1]==pytest.approx(b.controls[0])
    assert c.reversed().reversed()==c
    p=project().patch
    assert p.bezier_length(a.native()).value+p.bezier_length(b.native()).value==pytest.approx(p.bezier_length(c.native()).value)
    assert len(MetricCurve('a'*128,((0,0),(.1,0))).split(.5)[1].name)<=128


def test_transform_and_domain_validation_are_atomic():
    p=project(); h=MetricHistory(p)
    c=p.curves[0].transformed(dx=.1,angle=.2,factor=.8)
    q=p.put_curve(c); assert q.curves[0]==c
    with pytest.raises(ValueError): p.put_curve(c.transformed(dx=3))
    assert h.current==p
    with pytest.raises(ValueError): p.with_patch(NormalMetricPatch(radius=.1))
    assert p.patch.radius==1


@pytest.mark.parametrize('change',[{'version':True},{'version':2},{'schema':'wrong'},
                                   {'extra':0},{'curves':{}},{'name':''}, {'patch':None},
                                   {'curves':[{'name':'x','controls':[[0,0]],'extra':0}]}])
def test_invalid_schemas(change):
    obj=json.loads(project().to_json()); obj.update(change)
    with pytest.raises((ValueError,TypeError)): MetricProject.from_json(json.dumps(obj))


@pytest.mark.parametrize('controls',[[],[[True,0]],[[float('nan'),0]],[[0,0,0]],'eval()',[[float('inf'),1]]])
def test_bad_curve_controls(controls):
    with pytest.raises(ValueError): MetricCurve('c',controls)


def test_duplicates_and_outside_points():
    p=project(); obj=json.loads(p.to_json()); obj['curves']*=2
    with pytest.raises(ValueError): MetricProject.from_json(json.dumps(obj))
    with pytest.raises(ValueError): MetricProject(p.patch,(MetricCurve('bad',((2,0),)),))
    text=p.to_json().replace('"version": 1','"version": 1, "version": 1')
    with pytest.raises(ValueError): MetricProject.from_json(text)
    with pytest.raises(ValueError): MetricProject.from_json(' '*2_000_001)
    with pytest.raises(ValueError): MetricProject.from_json('['*1500)


def test_invalid_limits_and_unknown_unit():
    with pytest.raises(ValueError): MetricHistory(limit=True)
    with pytest.raises(ValueError): project().convert_units('survey feet')
