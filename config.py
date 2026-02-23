import pandas as pd
import database

ahora = pd.Timestamp.now(tz='Europe/Madrid')
config=database.get_config()
