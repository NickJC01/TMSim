# TMSim

This program simulates a 1-tape or 2-tape deterministic Turing Machine.
You can load a machine from a text file or type rules directly into the editor.
You choose the number of tapes, the input string w, and the initial state in the UI.

This code borrowed heavily from the Turing Machine logic and technical details available from [Morphett](https://morphett.info/turing/), so we give thanks to the contributors at Morphett for their hard work.

Test input Turing machines can be found in the parent directory of the program under "Testfiles"

The blank symbol is always: _
Spaces in the input are treated as blanks.

How to use the UI:
	1. Choose "Tapes" = 1 or 2
	2. Enter the input string in "input w"
   		- Example inputs: 010011, ababba
	3. Enter the starting state in "Initial state"
	4. Paste rules into the program box OR click "Load TM File..." to load a rule file
	5. Use run buttons:
   		- Step: run one transition
   		- Run: run continuously
   		- Pause: stop running
   		- Speed (ms): delay between steps while running. Higher value = slower runtime

The right side shows the tapes. a '^' character denotes the tape head.
The move log shows each transition at it's applied

TM file (or editor box) should contain ONLY rules and comments

- Symbols are single characters: 0, 1, a, b, _, etc.
- '_' is a blank.
- '\*literal asterisk\*' is a wildcard, "*" is NOT blank.

Moves:
Use one of these:
- l  = move left
- r  = move right
- '\*literal asterisk\*'  = do not move

Halting:
Any state name that starts with "halt" will halt the machine.
Examples: halt, halt-accept, halt-reject

Wildcards (\*literal asterisk\*) can be used in rules:

Read wildcard:
	- '\*literal asterisk\*' in a READ position matches any symbol in that tape cell.
Write wildcard:
	- '\*literal asterisk\*' in a WRITE position means "leave the symbol unchanged" on that tape.
Next state wildcard:
	- If next state is '\*literal asterisk\*', the machine stays in the same state.

Breakpoint (!): You can end a rule with '!' to pause after that rule is executed like found in the Morphett system.

Example:
0 1 1 r 0 !

Each 1-tape rule has 5 tokens (plus optional '!'):

<state> <read> <write> <move> <next_state> [!]

Example 1-tape machine: scan right, then halt
---------------------------------------------
; Format (1-tape): state read write move next

0 0 0 r 0
0 1 1 r 0
0 _ _ * halt
---------------------------------------------

Each 2-tape rule has 8 tokens (plus optional '!'):

<state> <read1> <read2> <write1> <write2> <move1> <move2> <next_state> [!]

Example 2-tape machine: copy tape1 to tape2, then halt
------------------------------------------------------
; Format (2-tape): state read1 read2 write1 write2 move1 move2 next

0 0 _ 0 0 r r 0
0 1 _ 1 1 r r 0
0 _ _ _ _ \*literal asterisk\* '\*literal asterisk\*' halt
---------------------------------------------
