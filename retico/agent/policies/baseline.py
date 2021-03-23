from retico.agent.frontal_cortex import FrontalCortexBase


class FC_Baseline(FrontalCortexBase):
    def trigger_user_turn_off(self):
        ret = False
        if self.cns.user_turn_active:
            if not self.cns.vad_ipu_active and not self.cns.asr_active:
                # self.cns.finalize_user()
                ret = True
        return ret


class FC_BaselineVad(FrontalCortexBase):
    def trigger_user_turn_off(self):
        ret = False
        if self.cns.user_turn_active:
            if not self.cns.vad_ipu_active:
                # self.cns.finalize_user()
                ret = True
        return ret
