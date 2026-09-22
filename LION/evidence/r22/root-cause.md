# LION R22 — Work to Project Chat migration

The prior R21 guard produced a false negative: the active OpenAI project conversation was still Work. The live UI does not expose Work through the route or the previously inspected pressed/selected attributes. The authoritative control is a project-level radiogroup labelled "Wybierz obszar czatu" with two radio buttons: Chat and Work. Live measurement showed Chat=data-state off and Work=data-state on.

R22 froze automatic dispatch without cancelling the queued Model request, opened the LION_EVOLUSION project landing page, measured the real radio contract, selected Chat only, and created a new project conversation. The new ordinary Chat conversation is /c/6ab28c62-48dc-83eb-b2d5-8d56a071c32f. The previous Work conversation remains historical and is no longer the bound LION SaaS channel.

The old Model request expired during the controlled migration without ever being sent by the browser. Mission Control created one explicit semantic retry linked by retry_of_request_id. The existing panel user message was rebound to that retry rather than duplicated. The retry was sent exactly once into the new Chat conversation, completed through SentinelX, safely reacquired claim generation 2 for final response binding, and delivered back to the same panel thread with receipt 0fb8e83b24d3ffcf1bf863ef6ab4fc0769a3fe8a5b624c24037252ff5e069efd.

The migration also exposed two historical-accounting defects in the browser Store. TURN_LIMIT/TASK_BUDGET_EXHAUSTED and MISSION_BINDING_CONFLICT counted terminal RECONCILED/CANCELLED history. After several verification turns this permanently blocked new work and prevented a legitimate Work-to-Chat rebind. R22 changes those gates to count active records only. Terminal history remains stored for audit, idempotence and evidence.

Final live state:
- project LION_EVOLUSION
- route PROJECT_CONVERSATION
- bound conversation /c/6ab28c62-48dc-83eb-b2d5-8d56a071c32f
- experience CHAT
- work_selected=false
- header_work=false
- automatic dispatch enabled
- relay WAITING_NEW_PANEL_TURN
- pending broker requests 0

RESULT=PASS_PROJECT_CHAT_MIGRATION
