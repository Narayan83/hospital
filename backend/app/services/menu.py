from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.menu import Menu
from app.models.role_menu_permission import RoleMenuPermission
from app.models.user_role_mapping import UserRoleMapping
from app.repositories.menu import MenuRepository
from app.schemas.menu import MenuPermissions, MenuTreeNode


class MenuService:
    SUPER_ADMIN_ROLE = "Super Admin"

    def __init__(self, session: AsyncSession):
        self.repo = MenuRepository(session)
        self.session = session

    async def get_user_menu_tree(self, user_id: str) -> list[MenuTreeNode]:
        role_ids, is_super_admin = await self._get_user_roles(user_id)
        menus = await self.repo.list_all_active()

        if is_super_admin:
            permission_map = {
                menu.id: MenuPermissions(can_view=True, can_create=True, can_update=True, can_delete=True)
                for menu in menus
            }
        elif role_ids:
            permission_map = await self._merged_permissions(role_ids)
        else:
            permission_map = {}

        return self._build_tree(menus, parent_id=None, permission_map=permission_map, is_super_admin=is_super_admin)

    async def _get_user_roles(self, user_id: str) -> tuple[list[str], bool]:
        result = await self.session.execute(
            select(UserRoleMapping)
            .options(selectinload(UserRoleMapping.role))
            .where(UserRoleMapping.user_id == user_id)
        )
        mappings = result.scalars().all()
        role_ids: list[str] = []
        is_super_admin = False
        for mapping in mappings:
            if mapping.role and mapping.role.is_active:
                role_ids.append(mapping.role_id)
                if mapping.role.role_name == self.SUPER_ADMIN_ROLE:
                    is_super_admin = True
        return role_ids, is_super_admin

    async def _merged_permissions(self, role_ids: list[str]) -> dict[str, MenuPermissions]:
        result = await self.session.execute(
            select(RoleMenuPermission).where(RoleMenuPermission.role_id.in_(role_ids))
        )
        merged: dict[str, MenuPermissions] = {}
        for perm in result.scalars().all():
            current = merged.get(
                perm.menu_id,
                MenuPermissions(can_view=False, can_create=False, can_update=False, can_delete=False),
            )
            merged[perm.menu_id] = MenuPermissions(
                can_view=current.can_view or perm.can_view,
                can_create=current.can_create or perm.can_create,
                can_update=current.can_update or perm.can_update,
                can_delete=current.can_delete or perm.can_delete,
            )
        return merged

    def _build_tree(
        self,
        menus: list[Menu],
        parent_id: str | None,
        permission_map: dict[str, MenuPermissions],
        is_super_admin: bool,
    ) -> list[MenuTreeNode]:
        nodes: list[MenuTreeNode] = []
        siblings = sorted(
            [m for m in menus if m.parent_id == parent_id],
            key=lambda m: m.sort_order,
        )
        for menu in siblings:
            children = self._build_tree(menus, menu.id, permission_map, is_super_admin)
            perms = permission_map.get(
                menu.id,
                MenuPermissions(
                    can_view=is_super_admin,
                    can_create=is_super_admin,
                    can_update=is_super_admin,
                    can_delete=is_super_admin,
                ),
            )
            if perms.can_view or children:
                nodes.append(
                    MenuTreeNode(
                        id=menu.id,
                        code=menu.code,
                        label=menu.label,
                        icon=menu.icon,
                        sort_order=menu.sort_order,
                        legacy_mcode=menu.legacy_mcode,
                        legacy_form=menu.legacy_form,
                        parameters=menu.parameters,
                        permissions=perms if perms.can_view else MenuPermissions(can_view=True),
                        children=children,
                    )
                )
        return nodes
