from dao.parse_warning import run
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='move warnings from timout/non_timout to preprocess')
    parser.add_argument('--table', type=str, default='timout', help='timout or non_timout, default is timout; non_timout is filtered by feasible path (positive case)')
    parser.add_argument('--selected', type=bool, default=False, help='whether to select only the selected/sampled warnings')
    args = parser.parse_args()
    if args.table == 'timout':
        offset = 0
    else:
        offset = 100000 # timeout table with max id 63714
    run(args.table, args.selected, offset)