from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Tuple
import apeiron.utils as U
from pydantic import BaseModel


BASIC_PROXIES = ['fmp','fred','plotly']


class Frameworks(Enum):
    REFLEX = 'reflex'  # the default framework, used for building web applications
    STREAMLIT = 'streamlit'  # used for building data applications



##########################################################################
# Helper Data Structures
###########################################################################

@dataclass
class Demand:
    task: str  # the task that the user wants to accomplish with the app
    description: str  # an optional description of the task
    expected_outcome: str  # the expected outcome of the task
    ratio: float  # the ratio of this demand in the overall user base, need to renormalize the ratios
    rubric: str 

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the Demand instance to a dictionary.
        """
        return {
            'task': self.task,
            'description': self.description,
            'expected_outcome': self.expected_outcome,
            'ratio': self.ratio,
            'rubric': self.rubric
        }

    @classmethod
    def from_dict(cls, demand_dict: Dict[str, Any]) -> 'Demand':
        """
        Create a Demand instance from a dictionary.
        The dictionary should contain 'task', 'expected_outcome', and 'ratio'.
        """
        return cls(
            task=demand_dict['task'],
            expected_outcome=demand_dict['expected_outcome'],
            ratio=float(demand_dict['ratio']),
            description=demand_dict.get('description', ''),
            rubric=demand_dict.get('rubric', '')
        )
    
    @property
    def id(self) -> str:
        return U.str_to_id(self.task)
    
    @property
    def prompt(self) -> str:
        return f'''Task: {self.task}
Description: {self.description}
Expected Outcome: {self.expected_outcome}
Rubric: {self.rubric}
'''

@dataclass
class DemandList:
    _demands: List[Demand] = field(default_factory=list)

    @property
    def demands(self) -> List[Demand]:
        if len(self._demands) == 0:
            return None
        _sum = sum(demand.ratio for demand in self._demands)
        for demand in self._demands:
            demand.ratio /= _sum
        return self._demands
    
    @property
    def empty(self) -> bool:
        return not self._demands

    def to_dict(self) -> Dict[str, Any]:
        return {
            'demands': [d.to_dict() for d in self.demands] if self.demands else [],
        }

    @classmethod
    def from_list(cls, demands: List[Dict]) -> 'DemandList':
        return cls(_demands=[Demand.from_dict(d) for d in demands])

    @classmethod
    def from_dict(cls, demands_dict: Dict[str, Any]) -> 'DemandList':
        """
        Create a Demands instance from a dictionary.
        The dictionary should contain 'demands'.
        """
        demands = [Demand.from_dict(d) for d in demands_dict.get('demands', [])]
        return cls(_demands=demands)
    

@dataclass
class DemandLists:
    demand_lists: Dict[str, DemandList] = field(default_factory=dict) # persona: DemandList
    reasoning: str = ''  # an optional description of the demand lists, it is the reply from the agent


@dataclass
class Persona: # user profile
    name: str
    description: str #Dict[str, Any] 
    ratio: float  # the ratio of the user's profile in the overall user base
    demands: DemandList = None

    @property
    def id(self) -> str:
        return U.str_to_id(self.name)

    def to_dict(self, include_demands: bool = True) -> Dict[str, Any]:
        """
        Convert the Persona instance to a dictionary.
        """
        _dict = {
            'name': self.name,
            'description': self.description,
            'ratio': self.ratio,
            'demands': self.demands.to_dict() if self.demands and include_demands else None
        }
        return _dict

    @property
    def prompt(self) -> str:
        return f'''Name: {self.name}
Description: {self.description}
'''

    @classmethod
    def from_dict(cls, persona_dict: Dict[str, Any]) -> 'Persona':
        """
        Create a Persona instance from a dictionary.
        The dictionary should contain 'name', 'description', and 'ratio'.
        """
        return cls(
            name=persona_dict['name'],
            description=persona_dict['description'],
            ratio=persona_dict['ratio'],
            demands=DemandList.from_dict(persona_dict.get('demands', {}))
        )
 

@dataclass
class PersonaDistribution:
    name: str  # the name of the persona distribution, should be unique
    description: str  # the description of the persona distribution
    _personas: List[Persona] = field(default_factory=list)
    reasoning: str = ''  # reasoning about the DEMANDS

    def __post_init__(self):
        self.personas # validate the profile distribution

    @property
    def id(self) -> str:
        return U.str_to_id(self.name)

    @property
    def personas(self) -> Dict[str, Persona]:
        personas = {persona.name: persona for persona in self._personas}
        _sum = sum(persona.ratio for persona in self._personas)
        for i in personas: # renormalize the ratios
            personas[i].ratio /= _sum
        return personas
    
    @property
    def demands(self) -> DemandLists:
        demands = {}
        for persona in self.personas.values():
            demands[persona.name] = persona.demands
        return DemandLists(demand_lists=demands, reasoning=self.reasoning)

    def set_demands(self, demands: DemandLists):
        self.reasoning = demands.reasoning
        for name, persona in self.personas.items():
            assert name in demands.demand_lists, f"Demand list for persona '{name}' not found in provided demands."
            persona.demands = demands.demand_lists[name]
    
    @property
    def demands_set(self) -> bool:
        if not self._personas:
            return False
        for persona in self._personas:
            if not persona.demands or not persona.demands.demands:
                return False
        if not self.reasoning:
            return False
        return True

    def persona_sorted(self) -> List[Persona]:
        """
        Return the personas sorted by their ratio in descending order.
        """
        return sorted(self._personas, key=lambda p: p.ratio, reverse=True)
    
    def show(self):
        """
        Print the persona distribution in a readable format.
        """
        U.cprint(f"Persona Distribution: {self.name}", 'y')
        U.cprint(f"{self.description}",'y')
        for persona in self.persona_sorted():
            print(f"  - {persona.name} ({persona.ratio* 100:.1f}%): {persona.description}")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the PersonaDistribution instance to a dictionary.
        """
        return {
            'name': self.name,
            'description': self.description,
            'personas': [p.to_dict() for p in self._personas],
            'reasoning': self.reasoning
        }
    
    @property
    def demands_created(self) -> bool:
        """
        Check if the demands have been created for this persona distribution.
        """
        return all(persona.demands is not None and not persona.demands.empty for persona in self._personas)
    
    @classmethod
    def from_dict(cls, persona_distribution_dict: Dict[str, Any]) -> 'PersonaDistribution':
        """
        Create a PersonaDistribution instance from a dictionary.
        The dictionary should contain 'name', 'description', and 'personas'.
        """
        return cls(
            name=persona_distribution_dict['name'],
            description=persona_distribution_dict['description'],
            _personas=[Persona.from_dict(p) for p in persona_distribution_dict.get('personas', [])],
            reasoning=persona_distribution_dict.get('reasoning', '')
        )
    
    @property
    def json(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'personas': [{
                'name': p.name,
                'description': p.description,
                'ratio': p.ratio,
            } for p in self._personas]
        }
    
    @property
    def prompt(self) -> str:
        prompt = f"Target User Persona Distribution: {self.name}\nDescription: {self.description}\nPersonas:\n"
        for idx, persona in enumerate(self.persona_sorted()):
            prompt += f"  {idx + 1}. {persona.name} ({persona.ratio * 100:.1f}%): {persona.description}\n"
        return prompt
    
    def prompt_with_demands(self, pairs: list = None) -> str: # TODO: split is for control the splits 
        prompt = f"Target User Persona Distribution: {self.name}\nDescription: {self.description}\nPersonas:\n"
        for idx, persona in enumerate(self.persona_sorted()):
            prompt += f"  {idx + 1}. {persona.name} ({persona.ratio * 100:.1f}%): {persona.description}\n"
            if persona.demands and not persona.demands.empty:
                prompt += f"    Demands:\n"
                for demand in persona.demands.demands:
                    if pairs and (persona.id, demand.id) not in pairs:
                            continue
                    prompt += f"      - {demand.task} ({demand.ratio * 100:.1f}%): {demand.description}\n"
                    prompt += f"        Expected Outcome: {demand.expected_outcome}\n"
                    prompt += f"        Rubric: {demand.rubric}\n"
        return prompt


@dataclass
class PersonaDistributions:
    distributions: List[PersonaDistribution] = field(default_factory=list)
    reasoning: str = ''  # an optional description of the persona distributions, it is the reply from the agent

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the PersonaDistributions instance to a dictionary.
        """
        return {
            'distributions': [pd.to_dict() for pd in self.distributions],
            'reasoning': self.reasoning
        }
    
    @classmethod
    def from_dict(cls, persona_distributions_dict: Dict[str, Any]) -> 'PersonaDistributions':
        distributions = [PersonaDistribution.from_dict(pd) 
                         for pd in persona_distributions_dict['distributions']]
        return cls(
            distributions=distributions,
            reasoning=persona_distributions_dict.get('reasoning', '')
        )


@dataclass
class Scenario:
    name: str  # a unique name for the scenario, do not include this index part (e.g. Scenario #) in your name
    description: str  # the detailed description of the scenario
    category: str = ''  # the detailed category of the scenario
    personas: PersonaDistributions = None
    parent_category: str = '' 

    @property
    def id(self):
        return U.str_to_id(self.name)

    @classmethod
    def from_dict(cls, scenario_dict: Dict[str, str], load_personas: bool = True) -> 'Scenario':
        """
        Create a Scenario instance from a dictionary.
        The dictionary should contain 'name', 'description', and optionally 'category'.
        """
        return cls(
            name=scenario_dict['name'],
            description=scenario_dict['description'],
            category=scenario_dict.get('category', ''),
            personas=PersonaDistributions.from_dict(scenario_dict.get('personas', {})) if load_personas else None,
            parent_category=scenario_dict.get('parent_category', '')
        )
    
    def to_dict(self, save_personas = True) -> Dict[str, Any]:
        """
        Convert the Scenario instance to a dictionary.
        """
        return {
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'personas': self.personas.to_dict() if self.personas and save_personas else {},
            'parent_category': self.parent_category
        }
    
    def pair_prompt(self, persona_index: int = 0) -> str:
        assert self.personas, "Personas must be defined for the scenario to generate a pair prompt."
        assert 0 <= persona_index < len(self.personas.distributions), \
            f"Invalid persona index {persona_index}, must be between 0 and {len(self.personas.distributions) - 1}."
        persona = self.personas.distributions[persona_index]
        return f'{self.prompt}\n\n{persona.prompt}'
    
    @property
    def prompt(self) -> str:
        return f"Scenario: {self.name}\nCategory: {self.json['category']}\nDescription: {self.description}"

    @property
    def json(self):
        category = self.parent_category
        if self.category:
            if category:
                category = f'{category} > {self.category}'
            else:
                category = self.category
        category_words = [i.capitalize() for i in category.replace('_', ' ').split(' ')]
        return {
            'name': self.name,
            'description': self.description,
            'category': ' '.join(category_words),
        }



@dataclass
class ScenarioList:
    category: str  # the category of the scenario, e.g. 'finance', 'healthcare', 'education', etc.
    scenarios: List[Scenario]  
    reasoning: str = None  # an optional analysis of the breakdown of the scenarios

    def __post_init__(self):
        for scenario in self.scenarios:
            if not isinstance(scenario, Scenario):
                raise ValueError(f"All items in scenarios must be of type Scenario, got {type(scenario)}")
            scenario.parent_category = self.category

    @classmethod
    def from_list(cls, category: str, scenarios: List[Dict[str,str]], reasoning: str = None) -> 'ScenarioList':
        scenarios = [Scenario(name=s['name'], description=s['description'], category=s['category'], parent_category=category) for s in scenarios]
        return cls(category=category, scenarios=scenarios, reasoning=reasoning)

@dataclass
class ScenarioLists:
    scenario_lists: List[ScenarioList]  # a list of scenario lists, each with a category and a list of scenarios
    version: str = '1.0'  # the version of the scenario lists, default is '1.0'
    note: str = ''  # an optional note of the scenario lists

    @property
    def scenarios(self) -> Dict[str, Scenario]:
        return {sl.category: sl.scenarios for sl in self.scenario_lists}

    def show(self, category: str = None):
        """
        Print the scenario lists in a readable format.
        If category is provided, only show scenarios in that category.
        If verbose is True, show detailed information about each scenario.
        """
        if not category:
            print("Version:", self.version)
            print(self.note)
        for sl in self.scenario_lists:
            if category and sl.category != category:
                continue
            print(f"Category: {sl.category}")
            for scenario in sl.scenarios:
                print(f"  - {scenario.name} ({scenario.category})") 
                print(f"    Description: {scenario.description}")
                print()






# @dataclass
# class FeedbackBase:

#     @property
#     def prompt(self) -> str:
#         raise NotImplementedError("Subclasses must implement this method")
    
#     @classmethod
#     def from_dict(cls, json_data: Dict[str, Any]) -> 'FeedbackBase':
#         raise NotImplementedError("Subclasses must implement this method")
    