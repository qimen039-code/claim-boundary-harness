# Interaction Error Corpus Meta Index

This public template contains synthetic routing structure only. Keep real
machine and project evidence in a private local overlay.

| Lane | Activation condition | Index |
| --- | --- | --- |
| structured-tool-control | A structured tool, connector, MCP, API, or direct application call is selected. | `structured-tool-control/_INDEX.md` |
| browser-control | Browser navigation, DOM, accessibility, or authenticated browser state is selected. | `browser-control/_INDEX.md` |
| desktop-app-control | A native desktop application or visual-only surface is selected. | `desktop-app-control/_INDEX.md` |
| keyboard-mouse-control | Deterministic keyboard or pointer input is the selected last suitable surface. | `keyboard-mouse-control/_INDEX.md` |

Read one lane index and at most two matching records. Open one adjacent lane
only when the active fallback changes control surface.
