from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SamplingRes(Base):
    __tablename__ = 'sampling_res'
    
    id = Column(Integer, primary_key=True)  # referencing id from CaseSampling
    model = Column(String, primary_key=True)  # make model part of the primary key
    result = Column(String)
    group = Column('group', Integer)  # As 'group' is a reserved keyword, provide it as a string
    initializer = Column(String)
    stable = Column(Boolean)
