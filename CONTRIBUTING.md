# Contributing

Reports from other Legion 5 15IAX10 units (other BIOS versions, other panels, the Intel-only variants) are what helps: which parts of the table worked, the OpenCore log (`opencore-*.txt` from a DEBUG build, with your serial, MLB, UUID and ROM removed) and `ioreg -l` where relevant. Other Arrow Lake-HX Lenovo models are welcome too, with the model named in the issue.

Pull requests: small, one change each, with the boot you tested it on. Never include a real SMBIOS identity, MAC address or recovery key. AI-assisted PRs are fine as long as you can explain the change, which is the same bar I hold my own code to.
