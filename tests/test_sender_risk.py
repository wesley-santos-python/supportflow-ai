"""Testes da heurística anti-fraude de remetente e do filtro de arquivos reais."""
from src.core.attachments import is_real_file
from src.core.sender_risk import assess_sender, extract_email


class TestSenderRisk:
    def test_bank_on_free_provider_is_high_risk(self):
        r = assess_sender("bancotal22332211@gmail.com")
        assert r["level"] == "alto"
        assert r["reasons"]  # explica o motivo

    def test_legit_bank_domain_is_ok(self):
        assert assess_sender("atendimento@itau.com.br")["level"] == "ok"

    def test_suspicious_tld_flagged(self):
        assert assess_sender("premios-sorteio@promo.top")["level"] in {"alto", "medio"}

    def test_regular_person_is_ok(self):
        assert assess_sender("joao.silva@gmail.com")["level"] == "ok"

    def test_extract_email_from_named_sender(self):
        assert extract_email('"Apple Suporte" <no-reply@apple.com>') == "no-reply@apple.com"


class TestRealFile:
    def test_real_files_pass(self):
        assert is_real_file("contrato.pdf")
        assert is_real_file("foto.JPG")
        assert is_real_file("planilha.xlsx")

    def test_non_files_rejected(self):
        assert not is_real_file("smime.p7s")
        assert not is_real_file("winmail.dat")
        assert not is_real_file("")
        assert not is_real_file("sem_extensao")


class TestHtmlToText:
    def test_strips_tags_and_styles(self):
        from src.core.automation import _html_to_text

        assert _html_to_text("<p>Olá <b>mundo</b></p>") == "Olá mundo"
        assert _html_to_text("<style>x{color:red}</style><p>oi</p>") == "oi"
        assert _html_to_text("") == ""
