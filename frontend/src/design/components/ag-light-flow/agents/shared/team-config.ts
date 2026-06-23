import maasLegalDesignTeam from '../../../../../../../../JSON_MODULES/teams/041_MAAS_Legal_Design_Team.json';

export interface JsonModuleParticipant {
  provider: string;
  component_type: 'agent' | string;
  label: string;
  description?: string;
  config: {
    name: string;
    description?: string;
    system_message?: string;
    handoffs?: string[];
  };
}

export interface JsonModuleTeam {
  provider: string;
  component_type: 'team' | string;
  label: string;
  description?: string;
  config: {
    name: string;
    description?: string;
    participants: JsonModuleParticipant[];
    selector_prompt?: string;
  };
}

export const MAAS_LEGAL_DESIGN_TEAM = maasLegalDesignTeam as JsonModuleTeam;

export const getTeamParticipants = (): JsonModuleParticipant[] =>
  MAAS_LEGAL_DESIGN_TEAM.config.participants;

export const getTeamParticipant = (name: string): JsonModuleParticipant => {
  const participant = getTeamParticipants().find((item) => item.config.name === name);
  if (!participant) {
    throw new Error(`Missing JSON_MODULES MAAS participant: ${name}`);
  }
  return participant;
};
