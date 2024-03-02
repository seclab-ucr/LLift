import unittest
from helper.get_func_def import *
import json


class TestPreprocess(unittest.TestCase):
    # def testReadFuncDef(self):
    #     file_path = 'lib/vsprintf.c'
    #     line_number = 3021
    #     print(read_function_definition(file_path, line_number))

    # def testGetFuncLoc(self):
    #     func_name = 'vsprintf'
    #     print(get_func_loc(func_name))
    #     func_name = 'ov5693_detect'
    #     print(get_func_loc(func_name))
    #     func_name = 'cmci_reenable'
    #     print(get_func_loc(func_name))

    tests = [
        {
            "callsite": "unlocked_inode_to_wb_begin(inode, &locked)",
            "suspicous": [
                "locked"
            ],
            "afc": None
        },
        {
            "callsite": "lock_page_lru(page, &isolated)",
            "suspicous": [
                "isolated"
            ],
            "afc": "lrucare"
        },
        {
            "callsite": "v4l2_subdev_call(cx->sd_av, vbi, decode_vbi_line, &vbi)",
            "suspicous": [
                "vbi.type"
            ],
            "afc": None
        },
        {
            "callsite": "fetch_pte(dom, bus_addr, &unmap_size)",
            "suspicous": [
                "unmap_size"
            ],
            "afc": None
        },
        {
            "callsite": "ov5693_read_reg(client, OV5693_8BIT, OV5693_SC_CMMN_CHIP_ID_L, &low)",
            "suspicous": [
                "low"
            ],
            "afc": "!ret"
        },
        {
            "callsite": "assoc_array_walk(array, ops, index_key, &result)",
            "suspicous": [
                "result"
            ],
            "afc": None
        },
        {
            "callsite": "btrfs_comp_cpu_keys(&item->key, &ins->key)",
            "suspicous": [
                "&item->key"
            ],
            "afc": None
        },
        {
            "callsite": "btrfs_init_free_space_ctl()",
            "suspicous": [
                "BITS_PER_BITMAP"
            ],
            "afc": None
        },
        {
            "callsite": "unlocked_inode_to_wb_begin(inode, &locked)",
            "suspicous": [
                "locked"
            ],
            "afc": None
        },
        {
            "callsite": "nlmsg_new(NLMSG_DEFAULT_SIZE, gfp)",
            "suspicous": [
                "msg"
            ],
            "afc": "!msg"
        },
        {
            "callsite": "cx2341x_ctrl_query(&cptr->hdw->enc_ctl_state, &qctrl)",
            "suspicous": [
                "qctrl.flags"
            ],
            "afc": None
        },
        {
            "callsite": "mt9m114_read_reg(client, MISENSOR_16BIT, (u32)MT9M114_PID, &retvalue)",
            "suspicous": [
                "retvalue"
            ],
            "afc": None
        },
        {
            "callsite": "bt_for_each(hctx, &tags->bitmap_tags, fn, priv, false)",
            "suspicous": [
                "&tags->bitmap_tags"
            ],
            "afc": None
        },
        {
            "callsite": "ec_read(addr, &value)",
            "suspicous": [
                "value"
            ],
            "afc": None
        }
    ]

    def testGetFuncDefEasy(self):
        func_name = 'vsprintf'
        print(get_func_def_easy(func_name))
        func_name = 'ov5693_detect'
        print(get_func_def_easy(func_name))
        func_name = 'cmci_reenable'
        print(get_func_def_easy(func_name))
        # --------------------more tests
        print(get_func_def_easy("regmap_read"))
        print(get_func_def_easy("_regmap_read"))
        print(get_func_def_easy("unlocked_inode_to_wb_begin"))

        print(get_func_def_easy("ext4_mb_simple_scan_group"))

        # --------------------more and more tests
        for test in self.tests:
            x = test['callsite']
            print(x.split('(')[0], ":")
            res = get_func_def_easy(x.split('(')[0])
            self.assertIsNotNone(res)
