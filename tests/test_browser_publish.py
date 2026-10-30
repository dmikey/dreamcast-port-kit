"""A rebuild publishes a loader only after its immutable WASM is complete."""
from pathlib import Path
import hashlib,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from browser import publish_bundle
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
