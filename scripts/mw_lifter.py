"""Project-local x87 correction for the shared pcrecomp lifter.

FCOM/FUCOM/FTST update the x87 status word, not integer EFLAGS. MW's
0x81CDC6 sound routine schedules CMP channel,-1; FUCOMPP; JNE: replacing
the CMP flags sends the all-channel sentinel through a single-channel write,
overwriting its effects callback at voice+0x118 with a floating-point gain.
Keep the integer lazy flags until TEST/SAHF explicitly transfers the status.
"""
from lift32 import Lifter as BaseLifter


class Lifter(BaseLifter):
    def _lift_instruction(self, insn):
        if insn.mnemonic not in {'fcom', 'fcomp', 'fcompp',
                                 'fucom', 'fucomp', 'fucompp', 'ftst'}:
            return super()._lift_instruction(insn)
        state, seq = self._flag_state, self._flag_seq
        lines = super()._lift_instruction(insn)
        self._flag_state, self._flag_seq = state, seq
        return [line for line in lines
                if line != '_flag_a = (uint32_t)_fpu_cmp; _flag_b = 0;']
