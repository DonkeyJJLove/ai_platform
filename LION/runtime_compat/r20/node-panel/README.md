# LION R20 Node panel runtime compatibility

This directory materializes the exact live Node secure-MCP producer observed on MOON during R20. The live producer is node_panel/src/secure-mcp-relay.js, not the historical Python relay. R20 adds causal parent_event_id=saas_request:<request_id> to the turn payload and metadata. The field is transport provenance only and grants no authority.

The live 8780 Node/Express panel was restarted against the same thread database and existing local gpt-oss-20b-MXFP4 endpoint. The copied relay test passed natively under Windows Node before the runtime relay was restarted.
