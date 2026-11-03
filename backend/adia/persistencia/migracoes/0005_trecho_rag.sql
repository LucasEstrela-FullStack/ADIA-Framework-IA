-- Proveniência do RAG (R26.4): qual trecho do corpus, em qual versão do índice, entrou no
-- pedido de uma dica gerada. Nulo em dica pré-escrita, em L1 e quando não há índice.
ALTER TABLE evento ADD COLUMN trecho_rag TEXT;
