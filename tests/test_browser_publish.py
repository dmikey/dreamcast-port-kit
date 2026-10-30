"""A rebuild publishes a loader only after its immutable WASM is complete."""
from pathlib import Path
import hashlib,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from browser import publish_bundle,publish_web_assets
class BrowserPublishTests(unittest.TestCase):
 def test_loader_keeps_previous_bundle_addressable(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);previous=None
   for data in (b'old complete wasm',b'new complete wasm'):
    (root/'game.next.wasm').write_bytes(data)
    (root/'game.next.js').write_text('fetch("game.next.wasm")')
    publish_bundle(root)
    name='game-'+hashlib.sha256(data).hexdigest()[:16]+'.wasm'
    self.assertEqual((root/name).read_bytes(),data)
    self.assertIn(name,(root/'game.js').read_text())
    if previous:self.assertTrue((root/previous).exists())
    previous=name

 def test_web_entrypoints_and_escaped_disc_title(self):
  import json
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);project=root/'project';output=root/'web';project.mkdir();output.mkdir()
   (project/'port.json').write_text(json.dumps({'disc':{'title':'<img src=x onerror=alert(1)>'}}))
   publish_web_assets(Path(__file__).resolve().parents[1],project,output)
   page=(output/'index.html').read_text()
   self.assertIn('&lt;img src=x onerror=alert(1)&gt;',page)
   self.assertNotIn('<img src=x',page)
   self.assertTrue((output/'player.html').exists())
   self.assertTrue((output/'debug-bridge.js').exists())
