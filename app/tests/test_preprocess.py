import unittest
from dao.preprocess import Preprocess
import psycopg2
from common.config import DATABASE_CONFIG
from prompts.call_api import warp_postcondition, warp_ret_value
import json

class TestPreprocess(unittest.TestCase):
    
    conn = psycopg2.connect(**DATABASE_CONFIG)

    # def test_fetch_all_preprocessed(self):
    #     cur = self.conn.cursor()
    #     cur.execute("SELECT preprocess FROM preprocess where preprocess.preprocess is not null")
    #     rows = cur.fetchall()
    #     self.assertTrue(len(rows) > 0)

    #     for row in rows:
    #         json_res = json.loads(row[0])
    #         print(json_res['callsite'].split('(')[0])
    

    def test_warp_postcondition(self):
        postcondition = "ret_val == 0"
        initializer = "int ret_val = __VERIFIER_nondet_int();"
        self.assertEqual(warp_postcondition(postcondition, initializer), "__VERIFIER_nondet_int() == 0")

        initializer = "int ret_val = __VERIFIER_nondet_int()"
        self.assertEqual(warp_postcondition(postcondition, initializer), "__VERIFIER_nondet_int() == 0")
        
        initializer = "offset = hidinput_find_field(hid, type, code, &field)"
        postcondition = "offset != -1"
        self.assertEqual(warp_postcondition(postcondition, initializer), "hidinput_find_field(hid, type, code, &field) != -1")

        postcondition = "offset != -1 && offset != 0"
        self.assertEqual(warp_postcondition(postcondition, initializer), "hidinput_find_field(hid, type, code, &field) != -1 && hidinput_find_field(hid, type, code, &field) != 0")

        initializer = "iint = integrity_iint_find(inode)"
        postcondition = "iint != NULL"
        self.assertEqual(warp_postcondition(postcondition, initializer), "integrity_iint_find(inode) != NULL")

        initializer = "decoder = devm_kzalloc(&client->dev, sizeof(*decoder), GFP_KERNEL)"
        postcondition = "decoder != NULL"
        self.assertEqual(warp_postcondition(postcondition, initializer), "devm_kzalloc(&client->dev, sizeof(*decoder), GFP_KERNEL) != NULL")


    def test_warp_ret_val(self):
        initializer =  "r = nci_hci_connect_gate(ndev, gates->dest_host, gates->gate, gates->pipe);"
        suspicious = ["r"]
        new_initializer = "func_ret_val = nci_hci_connect_gate(ndev, gates->dest_host, gates->gate, gates->pipe)"
        new_suspicious = ["func_ret_val"]
        self.assertEqual(warp_ret_value(suspicious, initializer), (new_suspicious, new_initializer))

        case2 = {"initializer": "sta = sta_info_get_bss(sdata, addr)", "suspicious": ["sta"], "postcondition": "null"}
        new_initializer = "func_ret_val = sta_info_get_bss(sdata, addr)"
        new_suspicious = ["func_ret_val"]
        self.assertEqual(warp_ret_value(case2["suspicious"], case2["initializer"]), (new_suspicious, new_initializer))