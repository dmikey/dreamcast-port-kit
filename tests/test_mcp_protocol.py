"""Standard stdio MCP discovery and schema rejection, using the official SDK."""
import importlib.util,unittest
from pathlib import Path

@unittest.skipUnless(importlib.util.find_spec('mcp'),'Install requirements-mcp.txt')
class MCPProtocolTests(unittest.IsolatedAsyncioTestCase):
 async def test_stdio_discovery_and_invalid_input(self):
  import sys
  from mcp import ClientSession,StdioServerParameters
  from mcp.client.stdio import stdio_client
  root=Path(__file__).resolve().parents[1]
  params=StdioServerParameters(command=sys.executable,args=[str(root/'mcp_server.py'),'--project',str(root/'.local/nonexistent-test-project')])
  async with stdio_client(params) as (read,write):
   async with ClientSession(read,write) as session:
    await session.initialize();result=await session.list_tools();tools={t.name:t for t in result.tools}
    self.assertEqual(len(tools),9);self.assertNotIn('eval',tools)
    schema=tools['press_button'].inputSchema['properties'];self.assertIn('Start',schema['button']['enum']);self.assertEqual(schema['duration_ms']['maximum'],5000)
    invalid=await session.call_tool('press_button',{'session_id':'test','button':'Start','duration_ms':6000})
    self.assertTrue(invalid.isError)
