import unittest
import sys
import os
import ast
import pandas as pd

test_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(test_dir, '..')))
# after all that tosh I can now nicely import my module :)
import positions

class BasicPositions(unittest.TestCase):

    def __init__(self, 
                 testName,
                 testmethodName, 
                 init_pos, 
                 deltas, 
                 board_size, 
                 other_peices=[], 
                 pos_answers=[], 
                 legal_answers=[],
                 *args,
                 **kwargs):
        super(BasicPositions, self).__init__(testmethodName)
        self.testName = testName
        self.init_pos = init_pos
        self.deltas = deltas
        self.board_size = board_size
        self.other_peices = other_peices
        self.pos_answers = pos_answers
        self.legal_answers = legal_answers

    def setUp(self):
        """setUp for {}""".format(self.testName)
        self.PosPos = positions.PosiblePositions(init_pos=self.init_pos,
                                                 deltas=self.deltas,
                                                 board_size=self.board_size,
                                                 other_peices=self.other_peices)

    def test_pos_positions(self):
        """test_pos_positions for {}""".format(self.testName)
        self.assertEqual(self.PosPos.pos_pos, self.pos_answers)
    
    def test_legal_positions(self):
        """
        test_legal_positions for {}
        """.format(self.testName)
        self.assertEqual(self.PosPos.legal_pos, self.legal_answers)


# call your test
suite = unittest.TestSuite()
# read test cases csv
test_cases = pd.read_csv(os.path.join(test_dir, 'position_tests.csv'))

for test_num, row in test_cases.iterrows():
    test_inputs = {}
    for k,v in row.to_dict().items():
        try:
            test_inputs[k] = ast.literal_eval(v)
        except ValueError:
            test_inputs[k] = v
    if test_inputs['pos_answers']:
        test_inputs["testmethodName"] = "test_pos_positions"
        suite.addTest(BasicPositions(**test_inputs))
    if test_inputs['legal_answers']:
        test_inputs["testmethodName"] = "test_legal_positions"
        suite.addTest(BasicPositions(**test_inputs))
    

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite)
