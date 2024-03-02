from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, func
from common.config import DB_CONFIG
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine(DB_CONFIG)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class PreprocessLog(Base):
    __tablename__ = 'preprocess_log'

    item_id = Column(Integer, primary_key=True)
    response1 = Column(Text)
    response2 = Column(Text)
    model = Column(String)
    respond_at = Column(DateTime, server_default=func.now())

    def commit(self, item_id, response1, response2, model):
        session = Session()
        self.item_id = item_id
        self.response1 = response1
        self.response2 = response2
        self.model = model
        session.add(self)
        session.commit()
        session.close()

class AnalysisLog(Base):
    __tablename__ = 'analysis_log'

    item_id = Column(Integer, primary_key=True)
    test_round = Column(Integer)
    dialog_id = Column(Integer)
    req_abstract = Column(Text)
    response = Column(Text)
    model = Column(String)
    response_at = Column(DateTime, server_default=func.now())

    def commit(self, item_id, test_round, dialog_id, req, response, model):
        session = Session()
        self.item_id = item_id
        self.test_round = test_round
        self.dialog_id = dialog_id
        self.req_abstract = req
        self.response = response
        self.model = model
        session.add(self)
        session.commit()
        session.close()
