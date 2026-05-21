"""
Resolver de dependências entre tabelas (FKs) para definir ordem de migração.

APIs expostas e já integradas no app:
- DependencyResolver.get_migration_order(excluded_tables: set | None) -> list[dict]
- DependencyResolver.analyze_dependencies() -> dict

Observações:
- Considera apenas FKs (Constraint.referenced_table_name não nulo)
- Ignora referências a tabelas que não estejam presentes na lista informada
- Marca ciclos e adiciona tabelas cíclicas ao final da ordenação (precisam de tratamento especial)
"""
from __future__ import annotations

from typing import List, Dict, Set

from dbmigrator.data_access.metadata_models import Table
from dbmigrator.migration_logging.log import MigrationLogger


class DependencyResolver:
	"""
	Analisa as dependências entre tabelas (por FKs) e calcula uma ordem de migração
	que respeite as tabelas pai antes das tabelas filhas.
	"""

	def __init__(self, tables: List[Table]):
		self.tables: List[Table] = tables or []
		self.table_dict: Dict[str, Table] = {t.name: t for t in self.tables if t and t.name}
		# dependency_graph[A] = {B, C} significa: A depende de B e C
		self.dependency_graph: Dict[str, Set[str]] = {}
		# reverse_graph[B] = {A} significa: A depende de B (ou seja, B é pai de A)
		self.reverse_graph: Dict[str, Set[str]] = {}

	def build_dependency_graph(self) -> Dict[str, Set[str]]:
		"""
		Constrói grafos de dependência com base nas FKs encontradas.
		"""
		self.dependency_graph = {name: set() for name in self.table_dict.keys()}
		self.reverse_graph = {name: set() for name in self.table_dict.keys()}

		for table in self.tables:
			if table is None or table.name not in self.table_dict:
				continue

			for constraint in getattr(table, 'constraints', []) or []:
				ref_table = getattr(constraint, 'referenced_table_name', None)
				if not ref_table:
					# Não é FK
					continue

				# Considere apenas dependências cujo alvo existe no conjunto
				if ref_table in self.table_dict:
					# table depende de ref_table (ref_table deve vir antes)
					self.dependency_graph[table.name].add(ref_table)
					self.reverse_graph[ref_table].add(table.name)

		MigrationLogger().log_info("Dependency graph built successfully")
		return self.dependency_graph

	def _dfs_cycle_detection(self, node: str, visited: Set[str], stack: Set[str], path: List[str], cycles: List[List[str]]):
		visited.add(node)
		stack.add(node)
		path.append(node)

		for neighbor in self.dependency_graph.get(node, set()):
			if neighbor not in visited:
				self._dfs_cycle_detection(neighbor, visited, stack, path, cycles)
			elif neighbor in stack:
				# Encontrou um ciclo
				try:
					start = path.index(neighbor)
					cycle = path[start:] + [neighbor]
				except ValueError:
					cycle = [neighbor, node, neighbor]
				if cycle and cycle not in cycles:
					cycles.append(cycle)

		stack.remove(node)
		path.pop()

	def detect_circular_dependencies(self) -> List[List[str]]:
		"""
		Detecta ciclos no grafo de dependências.
		"""
		visited: Set[str] = set()
		stack: Set[str] = set()
		cycles: List[List[str]] = []

		for name in self.dependency_graph.keys():
			if name not in visited:
				self._dfs_cycle_detection(name, visited, stack, [], cycles)

		return cycles

	def topological_sort(self) -> List[str]:
		"""
		Ordenação topológica (Kahn) das tabelas por dependência.
		Tabelas sem dependências entram primeiro. Em caso de ciclo, as tabelas remanescentes
		(com grau de entrada > 0) são adicionadas ao final.
		"""
		# Calcula grau de entrada (quantas dependências cada tabela tem)
		in_degree: Dict[str, int] = {}
		for name, deps in self.dependency_graph.items():
			in_degree[name] = len({d for d in deps if d in self.table_dict})

		queue = sorted([name for name, deg in in_degree.items() if deg == 0])
		ordered: List[str] = []

		while queue:
			current = queue.pop(0)
			ordered.append(current)

			for dependent in sorted(self.reverse_graph.get(current, set())):
				in_degree[dependent] -= 1
				if in_degree[dependent] == 0:
					queue.append(dependent)
					queue.sort()

		remaining = [n for n in self.dependency_graph.keys() if n not in ordered]
		if remaining:
			MigrationLogger().log_warning(f"Circular dependencies or unresolved in-degree. Appending: {remaining}")
			ordered.extend(sorted(remaining))

		MigrationLogger().log_info(f"Topological sort completed with {len(ordered)} tables")
		return ordered

	def get_migration_order(self, excluded_tables: Set[str] | None = None) -> List[Dict]:
		"""
		Retorna uma lista ordenada contendo objetos com metadados de migração por tabela.
		Campos: order, table_name, num_tuples, dependencies, dependents, has_circular_dependency
		"""
		excluded = excluded_tables or set()

		self.build_dependency_graph()
		order = self.topological_sort()

		# Marca ciclos
		cycles = self.detect_circular_dependencies()
		cyc_set: Set[str] = set()
		for c in cycles:
			for name in c:
				cyc_set.add(name)

		result: List[Dict] = []
		pos = 1
		for name in order:
			if name in excluded:
				continue
			t = self.table_dict.get(name)
			if not t or getattr(t, 'excluded', False):
				continue

			deps = sorted(self.dependency_graph.get(name, set()))
			dependents = sorted(self.reverse_graph.get(name, set()))

			result.append({
				"order": pos,
				"table_name": name,
				"num_tuples": t.num_tuples,
				"dependencies": deps,
				"dependents": dependents,
				"has_circular_dependency": name in cyc_set
			})
			pos += 1

		return result

	def analyze_dependencies(self) -> Dict:
		"""
		Retorna análise resumida: raízes, folhas, ciclos e top 10 por dependências e referências.
		"""
		self.build_dependency_graph()
		cycles = self.detect_circular_dependencies()

		root_tables = sorted([n for n, deps in self.dependency_graph.items() if len(deps) == 0])
		leaf_tables = sorted([n for n, ch in self.reverse_graph.items() if len(ch) == 0])

		most_dependencies = sorted(
			((n, len(d)) for n, d in self.dependency_graph.items()),
			key=lambda x: x[1], reverse=True
		)[:10]
		most_referenced = sorted(
			((n, len(ch)) for n, ch in self.reverse_graph.items()),
			key=lambda x: x[1], reverse=True
		)[:10]

		return {
			"total_tables": len(self.table_dict),
			"root_tables": root_tables,
			"leaf_tables": leaf_tables,
			"circular_dependencies": cycles,
			"most_dependencies": most_dependencies,
			"most_referenced": most_referenced,
		}
