# Source-bound operator desktop release selector

SOURCE_CANDIDATE_ONLY. This is a stable entrypoint for the original Electron R4/R11 application, not an updater or a new broker.

Start-LION.vbs routes the native Desktop shortcut to Start-LION-Current.ps1 under the operator profile. Start-LION-Current.ps1 reads the exact operator/current-release.json pointer, checks HEAD/TREE and SHA-256 of the versioned launcher, manifest and Electron main.cjs, and starts only that release after original launcher preflight. InspectOnly is read-only; ValidateOnly runs the selected release's original source preflight. Neither mode resumes the SaaS consumer.

PR454_CURRENT_RELEASE_EXAMPLE.json is a source example, not the currently activated release selector. Install-LION-Stable-Shortcut.ps1 -Mode Inspect is read-only. Its Install mode requires a separate exact operator approval, an original Windows user identity and existing PR #454 source files. It first preserves the original shortcut and then switches the Desktop entrypoint to the stable selector. The original Desktop shortcut still points to PR #432 until that action and independent readback.

The installed browser profile, broker.db, panel threads.db, historic versions and outstanding requests are never copied, cleared or automatically rebound. On any unknown source or failure, fail closed, inspect and reconcile before a new attempt. No automatic newest-directory choice or old-release fallback.

The original composition and source of SaaS responses/receipts are unchanged. Read the architecture owner document at LION/architecture/v1_5/DESKTOP_RELEASE_AND_CONVERSATION_CONTINUITY_R1.md.

Manual bridge note: opening the ChatGPT project landing does not create a durable external_thread_ref. The operator must select an existing concrete project conversation (or create one in ChatGPT itself) before accepting a native exact-thread binding. A bridge record still does not prove a SaaS response/receipt.
