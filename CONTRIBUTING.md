# Contribuindo para o SupportFlow AI

Obrigado pelo interesse em contribuir! 🎉

## Como Contribuir

### 1. Fork e Clone

```bash
git clone https://github.com/seu-usuario/supportflow-ai.git
cd supportflow-ai
```

### 2. Configure o Ambiente

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
cp .env.example .env
# Edite .env com suas credenciais
```

### 3. Crie uma Branch

```bash
git checkout -b feature/minha-feature
```

### 4. Faça suas Mudanças

- Siga o padrão de código existente
- Adicione testes para novas funcionalidades
- Atualize a documentação se necessário

### 5. Rode os Testes

```bash
pytest tests/ -v
```

### 6. Commit e Push

```bash
git add .
git commit -m "feat: descrição da mudança"
git push origin feature/minha-feature
```

### 7. Abra um Pull Request

## Padrão de Commits

- `feat:` Nova funcionalidade
- `fix:` Correção de bug
- `docs:` Documentação
- `test:` Testes
- `refactor:` Refatoração

## Dúvidas?

Abra uma issue! 💬
