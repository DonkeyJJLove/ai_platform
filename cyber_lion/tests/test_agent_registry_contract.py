from __future__ import annotations
import unittest
from cyber_lion.contracts.agent_registry import AgentInstance,AgentRegistryContractError
class ContractTests(unittest.TestCase):
 def test_terminal_state_contract(self):
  i=AgentInstance("i","a","v","0"*64,"REVOKED",1,"t","t",("e",));self.assertIs(i.validate(),i)
 def test_unknown_state_denied(self):
  with self.assertRaises(AgentRegistryContractError):AgentInstance("i","a","v","0"*64,"UNKNOWN",0,"t","t",("e",)).validate()
if __name__=="__main__":unittest.main()
