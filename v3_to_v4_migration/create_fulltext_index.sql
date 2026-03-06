-- Add fulltext index for search (online DDL)
SET SESSION sql_mode = '';

ALTER TABLE codes ADD FULLTEXT INDEX ft_search (title, abstract, credit), ALGORITHM=INPLACE, LOCK=SHARED;
