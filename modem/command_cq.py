from command import TxCommand
from codec2 import FREEDV_MODE
class CQCommand(TxCommand):

    def build_frame(self):
        return self.frame_factory.build_cq()

    def get_tx_mode(self):
        return FREEDV_MODE.data_ofdm_500
