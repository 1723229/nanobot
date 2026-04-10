from nanobot.config.schema import AgentDefaults, Config, SkillsConfig


def test_skills_config_defaults_are_conservative() -> None:
    cfg = SkillsConfig()

    assert cfg.enabled is True
    assert cfg.review_enabled is False
    assert cfg.review_mode == "auto_update"
    assert cfg.allow_delete is False


def test_agent_defaults_include_skills_config() -> None:
    defaults = AgentDefaults()

    assert isinstance(defaults.skills, SkillsConfig)
    assert defaults.skills.review_enabled is False


def test_config_serializes_skills_config_in_camel_case() -> None:
    data = Config().model_dump(mode="json", by_alias=True)

    assert "skills" in data["agents"]["defaults"]
    assert "reviewEnabled" in data["agents"]["defaults"]["skills"]


def test_config_parses_skills_config_from_camel_case() -> None:
    config = Config.model_validate({
        "agents": {
            "defaults": {
                "skills": {
                    "reviewEnabled": True,
                    "reviewMode": "auto_create",
                    "allowDelete": True,
                }
            }
        }
    })

    assert config.agents.defaults.skills.review_enabled is True
    assert config.agents.defaults.skills.review_mode == "auto_create"
    assert config.agents.defaults.skills.allow_delete is True
