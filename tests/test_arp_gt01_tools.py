"""CLI/import regressions; these tests do not build a complete car."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

EXAMPLE = Path(__file__).resolve().parents[1] / 'examples' / 'arp_gt01'
SCRIPTS = ('build_car.py', 'build_viewer.py', 'validate_car.py', 'render_car.py')


def load_script(name):
    spec = importlib.util.spec_from_file_location('arp_test_' + Path(name).stem, EXAMPLE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('name', SCRIPTS)
def test_import_does_not_run_cli_or_load_optional_dependencies(name, tmp_path):
    code = '''
import builtins, runpy, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in ('cadquery', 'OCP', 'vtk', 'numpy', 'PIL'):
        raise ImportError('optional dependency must not load during script import')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
runpy.run_path(sys.argv[1], run_name='import_test')
'''
    result = subprocess.run([sys.executable, '-c', code, str(EXAMPLE/name)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('name', SCRIPTS)
def test_help_from_another_working_directory(name, tmp_path):
    result = subprocess.run([sys.executable, str(EXAMPLE/name), '--help'], cwd=tmp_path,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert 'usage:' in result.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('value', ['0', '-1', 'nan', 'inf'])
def test_reject_bad_scale_before_creating_output(tmp_path, value):
    output = tmp_path / 'model'
    result = subprocess.run([sys.executable, str(EXAMPLE/'build_car.py'), '--scale', value,
                             '--out', str(output)], capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert 'positive and finite' in result.stderr
    assert not output.exists()


def test_embed_escapes_script_end_and_uses_utf8(tmp_path):
    module = load_script('build_viewer.py')
    destination = tmp_path / 'viewer.html'
    payload = {'name': '</script><script>alert(1)</script>', 'label': 'Bezier coupe'}
    template = tmp_path / 'template.html'
    template.write_text('<script>const M=__MODEL_JSON__;</script>', encoding='utf-8')
    module.write_viewer(template, payload, destination)
    html = destination.read_text(encoding='utf-8')
    assert html.count('</script>') == 1
    assert '\\u003c/script>' in html
    recovered = html.split('const M=')[1].split(';</script>')[0]
    assert json.loads(recovered) == payload
    template.write_text('no placeholder', encoding='utf-8')
    with pytest.raises(ValueError):
        module.write_viewer(template, payload, destination)


def test_validation_failure_replaces_stale_pass_even_under_optimization(tmp_path):
    (tmp_path/'ARP_GT01.design.json').write_text('{}', encoding='utf-8')
    report = tmp_path/'independent_validation.json'
    report.write_text('{"status":"PASS"}', encoding='utf-8')
    result = subprocess.run([sys.executable, '-O', str(EXAMPLE/'validate_car.py'),
                             '--model', str(tmp_path)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 1
    assert json.loads(report.read_text())['status'] == 'FAIL'


def test_viewer_stats_come_from_manifest():
    template = (EXAMPLE/'viewer_template.html').read_text(encoding='utf-8')
    assert template.count('__MODEL_JSON__') == 1
    assert 'MODEL.stats' in template
    assert '<b>345</b>' not in template
