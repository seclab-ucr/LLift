import logging
import argparse
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import json

from dao.case_sampling import CaseSampling
from dao.sampling_res import SamplingRes
from common.config import DB_CONFIG, EVAL_RES_TABLE
from prompts.call_api import do_preprocess, do_analysis

INF = 10000000  # a large number, 10M

# Create the engine
engine = create_engine(DB_CONFIG)
Session = sessionmaker(bind=engine)

# This function now uses SQLAlchemy to interact with the database


def fetch_all(session, group, max_id, min_id, offset, max_number):
    batch_size = 100

    # count the total number of relevant rows
    count_query = session.query(CaseSampling).filter(
        and_(
            CaseSampling.group == group,
            CaseSampling.var_name.notlike('%$%'),
            CaseSampling.id >= min_id,
            CaseSampling.id <= max_id
        )
    )

    real_max_num = count_query.count()
    max_number = min(max_number, real_max_num)

    logging.info(
        f"Total number: {real_max_num}, analyzing {max_number} functions..."
    )

    while offset < max_number:
        rows = count_query.order_by(CaseSampling.id).offset(
            offset).limit(batch_size).all()
        offset += batch_size
        yield rows


def fetch_and_update_ctx(group, max_id, min_id, offset, max_number):
    with Session() as session:
        logging.info("Connected to database...")
        for rows in fetch_all(session, group, max_id, min_id, offset, max_number):
            # Parse the fetched data
            for case in rows:
                if case.raw_ctx is not None and len(case.raw_ctx) > 0:
                    continue
                case.update_raw_ctx()
                if case.raw_ctx is None:
                    logging.error(
                        f"Failed to update raw_ctx for function {case.function}")
                    continue
                session.add(case)
                logging.info(
                    f"Updated raw_ctx for function {case.function} with context {case.raw_ctx[:20]}...")
            session.commit()


def result_stable_check(res, new_res):
    if res == new_res:
        return True
    
    try:
        res = json.loads(res)
        new_res = json.loads(new_res)
        if res['response']['must_init'] == new_res['response']['must_init']:
            return True
    except Exception:
        return False
    return False


def preprocess_and_analyze(group, max_id, min_id, offset, max_number, model, max_round):
    model = model + '--dev'
    with Session() as session:
        logging.info("Connected to database...")
        for rows in fetch_all(session, group, max_id, min_id, offset, max_number):
            for case in rows:
                # Skip case if raw context is missing or not enough rounds left
                if case.raw_ctx is None or len(case.raw_ctx) < 15 or case.last_round >= max_round:
                    continue

                logging.info(
                    f"Preprocessing function {case.function} with context {case.raw_ctx[:20]}...")

                # Preprocessing
                
                sampling_res = session.query(SamplingRes).filter(
                    SamplingRes.id == case.id, SamplingRes.model == model).first()
                
                # we allow small inconsistency between preprocessing results
                initializer = do_preprocess(case, model)
                if sampling_res:
                    initializer = sampling_res.initializer

                    if max_round != INF and case.last_round >= 2 and sampling_res.stable == True:
                        logging.info(
                            f"Skip analysis for function {case.function}, variable {case.var_name} with initializer {initializer[:100]}...")
                        continue
                else:
                    sampling_res = SamplingRes(
                        id=case.id, model=model, initializer=initializer, group=group, stable=True)
                
                session.add(sampling_res)
                
                # initializer = do_preprocess(case, model)

                logging.info(
                    f"analyzing {case.function}, variable {case.var_name} with initializer {initializer[:100]}...")

                result = do_analysis(sampling_res, case.last_round, case, model)

                if sampling_res.result and (not result_stable_check(sampling_res.result, result)):
                    sampling_res.stable = False
                    logging.error(
                        f"Analysis result for function {case.function} with variable {case.var_name} changed!!!")
                    logging.error(f"Old result: {sampling_res.result}")
                    logging.error(f"New result: {result}")
                # Analysis

                sampling_res.result = result  # Updating the result with analysis output

                if "error" in result and case.last_round > 0:
                    logging.error(
                        f"Failed to analyze function {case.function}, variable {case.var_name} with result {result[:100]}...")
                    continue

                logging.info(
                    f"Updated analysis for function {case.function}, variable {case.var_name} with result {result[:100]}...")
                logging.info("updating last_round")
                case.last_round = case.last_round + 1
                session.commit()


if __name__ == "__main__":
    # test_preprocess_read_file()
    logging.basicConfig(
        level=logging.INFO, format='%(asctime)s %(levelname)-s %(filename)s:%(lineno)s - %(funcName)20s() :: %(message)s')


    parser = argparse.ArgumentParser(
        description='using arguments to control the # of warnings in database to be processed')
    parser.add_argument('--group', type=int, required=True,
                        help='the group of experiment')
    parser.add_argument('--max_id', type=int, default=INF,
                        help='max id of the warning to be processed; default is INF, id is the original identify from static analysis of UBITect')
    parser.add_argument('--min_id', type=int, default=-INF,
                        help='min id of the warning to be processed; default is -INF')
    parser.add_argument('--offset', type=int, default=0,
                        help='offset of the warning to be processed')
    parser.add_argument('--max_number', type=int, default=INF,
                        help='max number of the warning to be processed; default is ifinite')
    parser.add_argument('--model', type=str, default='gpt-4-0314',
                        help='model to be used, default is gpt-4-0314')
    parser.add_argument('--max_round', type=int, default=1,
                        help="control the max running round of each case; increasing to test the stablity of output")
    parser.add_argument('--id', type=int, default=0, help="specifify the item to be processed \nNOTE: it will overwrite the max_id, min_id, offset, max_number, max_round")
    # parser.add_argument('--temperature', type=float, default=0.7,
    #                     help="control the max running round of each case; increasing to test the stablity of output")
    args = parser.parse_args()

    if args.id != 0:
        args.max_id = args.id
        args.min_id = args.id
        args.offset = 0
        args.max_number = 1
        args.max_round = INF

    fetch_and_update_ctx(args.group, args.max_id, args.min_id,
                         args.offset, args.max_number)
    # fetch_and_update_preprocess_result(
    #     args.group, args.max_id, args.min_id, args.offset, args.max_number, args.model)
    # fetch_and_update_analysis_result(
    #     args.group, args.max_id, args.min_id, args.offset, args.max_number, args.model)
    # conn.close()
    preprocess_and_analyze(args.group, args.max_id, args.min_id,
                           args.offset, args.max_number, args.model, args.max_round)
