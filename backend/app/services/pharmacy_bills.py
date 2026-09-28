from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient
from app.models.pharmacy import (
    PharmacyPurchaseBill,
    PharmacyPurchaseBillLine,
    PharmacySaleBill,
    PharmacySaleBillLine,
)
from app.repositories.pharmacy import PharmacyItemRepository, PharmacySupplierRepository
from app.repositories.pharmacy_bills import (
    PharmacyPurchaseBillRepository,
    PharmacySaleBillRepository,
    list_active_items,
    purchased_qty_by_item,
    sales_summary_by_item,
    schedule_h_sales,
    sold_qty_by_item,
)
from app.schemas.pharmacy import (
    PharmacyIndentCreate,
    PharmacyLastBillInfo,
    PharmacyPurchaseBillCreate,
    PharmacyPurchaseBillRead,
    PharmacySalesRegisterRow,
    PharmacySalesSummaryRow,
    PharmacySaleBillCreate,
    PharmacySaleBillRead,
    PharmacyScheduleHRow,
    PharmacyStockLookup,
    PharmacyStockRow,
)
from app.services.bill_number import BillNumberService


class PharmacyBillService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.sale_repo = PharmacySaleBillRepository(session)
        self.purchase_repo = PharmacyPurchaseBillRepository(session)
        self.item_repo = PharmacyItemRepository(session)
        self.supplier_repo = PharmacySupplierRepository(session)
        self.number_svc = BillNumberService(session)

    async def last_sale_bill_info(self) -> PharmacyLastBillInfo:
        last_no = await self.sale_repo.get_last_bill_no()
        return PharmacyLastBillInfo(last_bill_no=last_no, next_preview="Auto on Save")

    async def stock_lookup(self, code: str, item_type: str = "MD") -> PharmacyStockLookup:
        item = await self.item_repo.get_by_code(item_type.upper(), code.strip().upper())
        if not item or not item.is_active:
            matches = await self.item_repo.search(item_type.upper(), code, limit=1)
            item = matches[0] if matches else None
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        purchased = await purchased_qty_by_item(self.session)
        sold = await sold_qty_by_item(self.session)
        stock_qty = purchased.get(item.id, 0) - sold.get(item.id, 0)
        return PharmacyStockLookup(
            item_id=item.id,
            item_code=item.code,
            item_name=item.name,
            stock_qty=stock_qty,
            rate=item.sale_rate or item.mrp,
        )

    async def create_sale_bill(self, data: PharmacySaleBillCreate) -> PharmacySaleBillRead:
        bill_date = data.bill_date or date.today()
        patient_name = data.patient_name
        if data.patient_id:
            patient = await self.session.get(Patient, data.patient_id)
            if patient:
                patient_name = patient_name or patient.full_name

        lines_data = await self._resolve_sale_lines(data.lines)
        gross = sum(line["line_net"] for line in lines_data)
        discount = Decimal(str(data.discount_amount or 0))
        subtotal = gross - discount
        if subtotal < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Net amount cannot be negative")
        rounded_net = subtotal.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        round_off = Decimal(str(data.round_off if data.round_off is not None else rounded_net - subtotal))
        net = subtotal + round_off

        bill_no = await self.number_svc.generate_pharmacy_sale_bill_no(bill_date)
        bill = PharmacySaleBill(
            bill_no=bill_no,
            bill_date=bill_date,
            patient_id=data.patient_id,
            patient_name=patient_name,
            doctor_id=data.doctor_id,
            doctor_name=(data.doctor_name or "").strip() or None,
            scheme=(data.scheme or "").strip() or None,
            payment_mode_id=data.payment_mode_id,
            is_cash=data.is_cash,
            gross_amount=gross,
            discount_amount=discount,
            round_off=round_off,
            net_amount=net,
            address1=(data.address1 or "").strip() or None,
            address2=(data.address2 or "").strip() or None,
            address3=(data.address3 or "").strip() or None,
            remarks=data.remarks,
        )
        self.session.add(bill)
        await self.session.flush()

        for index, line in enumerate(lines_data):
            item = line["item"]
            self.session.add(
                PharmacySaleBillLine(
                    bill_id=bill.id,
                    item_id=item.id,
                    item_code=item.code,
                    item_name=item.name,
                    unit=item.unit,
                    schedule=item.schedule,
                    nos=line["nos"],
                    factor=line["factor"],
                    batch_no=line.get("batch_no"),
                    expiry_date=line.get("expiry_date"),
                    rate=line["rate"],
                    quantity=line["quantity"],
                    tax_percent=line["tax_percent"],
                    tax_amount=line["tax_amount"],
                    amount=line["amount"],
                    line_discount_percent=line["line_discount_percent"],
                    line_discount_amount=line["line_discount_amount"],
                    line_net=line["line_net"],
                    user1=line.get("user1"),
                    sort_order=index,
                )
            )
        await self.session.flush()
        saved = await self.sale_repo.get_with_lines(bill.id)
        return PharmacySaleBillRead.model_validate(saved)

    async def create_purchase_bill(self, data: PharmacyPurchaseBillCreate) -> PharmacyPurchaseBillRead:
        bill_kind = (data.bill_kind or "purchase").strip().lower()
        if bill_kind not in {"purchase", "return"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid bill kind")

        if data.supplier_id:
            supplier = await self.supplier_repo.get_by_id(data.supplier_id)
            if not supplier or not supplier.is_active:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid supplier")

        bill_date = data.bill_date or date.today()
        lines_data = await self._resolve_lines(data.lines, default_rate_field="purchase_rate")

        if bill_kind == "return":
            purchased = await purchased_qty_by_item(self.session)
            sold = await sold_qty_by_item(self.session)
            for line in lines_data:
                item = line["item"]
                stock = purchased.get(item.id, 0) - sold.get(item.id, 0)
                qty = int(line["quantity"])
                if qty > stock:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Insufficient stock for {item.code} (available {stock}, return {qty})",
                    )

        gross = sum(line["amount"] for line in lines_data)
        bill_no = await self.number_svc.generate_pharmacy_purchase_bill_no(bill_date)
        if bill_kind == "return" and not bill_no.upper().startswith("PR"):
            # Keep same series; mark in remarks for clarity.
            pass
        remarks = data.remarks
        if bill_kind == "return":
            prefix = "PURCHASE RETURN"
            remarks = f"{prefix}. {remarks}" if remarks else prefix

        bill = PharmacyPurchaseBill(
            bill_no=bill_no,
            bill_date=bill_date,
            supplier_id=data.supplier_id,
            invoice_no=data.invoice_no,
            gross_amount=gross,
            net_amount=gross,
            remarks=remarks,
            bill_kind=bill_kind,
        )
        self.session.add(bill)
        await self.session.flush()

        for index, line in enumerate(lines_data):
            self.session.add(
                PharmacyPurchaseBillLine(
                    bill_id=bill.id,
                    item_id=line["item"].id,
                    item_code=line["item"].code,
                    item_name=line["item"].name,
                    unit=line["item"].unit,
                    rate=line["rate"],
                    quantity=line["quantity"],
                    amount=line["amount"],
                    batch_no=line.get("batch_no"),
                    expiry_date=line.get("expiry_date"),
                    sort_order=index,
                )
            )
        await self.session.flush()
        saved = await self.purchase_repo.get_with_lines(bill.id)
        return PharmacyPurchaseBillRead.model_validate(saved)

    async def create_indent(self, data: PharmacyIndentCreate) -> PharmacySaleBillRead:
        """Issue medicines to a ward (reduces pharmacy stock like an internal sale)."""
        ward = (data.ward_name or "").strip()
        if not ward:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ward is required")

        # Validate stock before issuing.
        purchased = await purchased_qty_by_item(self.session)
        sold = await sold_qty_by_item(self.session)
        for line in data.lines:
            item = await self.item_repo.get_by_id(line.item_id)
            if not item or not item.is_active:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid item")
            stock = purchased.get(item.id, 0) - sold.get(item.id, 0)
            if line.quantity > stock:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient stock for {item.code} (available {stock}, indent {line.quantity})",
                )

        remarks = data.remarks.strip() if data.remarks else ""
        remarks = f"INDENT|{ward}" + (f"|{remarks}" if remarks else "")
        sale_data = PharmacySaleBillCreate(
            patient_name=f"INDENT — {ward}",
            is_cash=False,
            remarks=remarks,
            bill_date=data.bill_date,
            lines=data.lines,
        )
        return await self.create_sale_bill(sale_data)

    async def get_sale_bill(self, bill_id: str) -> PharmacySaleBillRead:
        bill = await self.sale_repo.get_with_lines(bill_id)
        if not bill:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale bill not found")
        return PharmacySaleBillRead.model_validate(bill)

    async def get_purchase_bill(self, bill_id: str) -> PharmacyPurchaseBillRead:
        bill = await self.purchase_repo.get_with_lines(bill_id)
        if not bill:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase bill not found")
        return PharmacyPurchaseBillRead.model_validate(bill)

    async def sales_register(self, from_date: date, to_date: date) -> list[PharmacySalesRegisterRow]:
        bills = await self.sale_repo.list_by_date_range(from_date, to_date)
        return [
            PharmacySalesRegisterRow(
                bill_no=bill.bill_no,
                bill_date=bill.bill_date,
                patient_name=bill.patient_name,
                item_count=len(bill.lines),
                gross_amount=bill.gross_amount,
                discount_amount=bill.discount_amount,
                net_amount=bill.net_amount,
            )
            for bill in bills
        ]

    async def sales_summary(self, from_date: date, to_date: date) -> list[PharmacySalesSummaryRow]:
        rows = await sales_summary_by_item(self.session, from_date, to_date)
        return [
            PharmacySalesSummaryRow(
                item_code=row[0],
                item_name=row[1],
                total_qty=int(row[2]),
                total_amount=Decimal(str(row[3])),
            )
            for row in rows
        ]

    async def schedule_h_report(self, from_date: date, to_date: date) -> list[PharmacyScheduleHRow]:
        rows = await schedule_h_sales(self.session, from_date, to_date)
        return [
            PharmacyScheduleHRow(
                bill_no=row[0],
                bill_date=row[1],
                patient_name=row[2],
                item_code=row[3],
                item_name=row[4],
                schedule=row[5] or "",
                quantity=int(row[6]),
                amount=Decimal(str(row[7])),
            )
            for row in rows
        ]

    async def consolidated_stock_report(self) -> list[PharmacyStockRow]:
        purchased = await purchased_qty_by_item(self.session)
        sold = await sold_qty_by_item(self.session)
        items = await list_active_items(self.session)
        rows: list[PharmacyStockRow] = []
        for item in items:
            purchased_qty = purchased.get(item.id, 0)
            sold_qty = sold.get(item.id, 0)
            rows.append(
                PharmacyStockRow(
                    item_type=item.item_type,
                    item_code=item.code,
                    item_name=item.name,
                    unit=item.unit,
                    purchased_qty=purchased_qty,
                    sold_qty=sold_qty,
                    balance_qty=purchased_qty - sold_qty,
                    reorder_level=item.reorder_level,
                )
            )
        return rows

    async def _resolve_sale_lines(self, lines) -> list[dict]:
        resolved: list[dict] = []
        for line in lines:
            item = await self.item_repo.get_by_id(line.item_id)
            if not item or not item.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid pharmacy item: {line.item_id}",
                )
            default_rate = item.sale_rate or item.mrp or Decimal("0")
            rate = Decimal(str(line.rate if line.rate is not None else default_rate))
            qty = line.quantity
            nos = line.nos or 1
            factor = Decimal(str(line.factor or 1))
            amount = (Decimal(nos) * factor * Decimal(qty) * rate).quantize(Decimal("0.01"))
            tax_percent = Decimal(str(line.tax_percent or 0))
            tax_amount = (
                Decimal(str(line.tax_amount))
                if line.tax_amount is not None
                else (amount * tax_percent / Decimal("100")).quantize(Decimal("0.01"))
            )
            dis_percent = Decimal(str(line.line_discount_percent or 0))
            dis_amount = (
                Decimal(str(line.line_discount_amount))
                if line.line_discount_amount is not None
                else (amount * dis_percent / Decimal("100")).quantize(Decimal("0.01"))
            )
            line_net = (
                Decimal(str(line.line_net))
                if line.line_net is not None
                else (amount + tax_amount - dis_amount).quantize(Decimal("0.01"))
            )
            resolved.append(
                {
                    "item": item,
                    "rate": rate,
                    "quantity": qty,
                    "nos": nos,
                    "factor": factor,
                    "amount": amount,
                    "tax_percent": tax_percent,
                    "tax_amount": tax_amount,
                    "line_discount_percent": dis_percent,
                    "line_discount_amount": dis_amount,
                    "line_net": line_net,
                    "batch_no": line.batch_no,
                    "expiry_date": line.expiry_date,
                    "user1": (line.user1 or "").strip() or None,
                }
            )
        return resolved

    async def _resolve_lines(self, lines, *, default_rate_field: str) -> list[dict]:
        resolved: list[dict] = []
        for line in lines:
            item = await self.item_repo.get_by_id(line.item_id)
            if not item or not item.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid pharmacy item: {line.item_id}",
                )
            default_rate = getattr(item, default_rate_field) or item.mrp or Decimal("0")
            rate = Decimal(str(line.rate if line.rate is not None else default_rate))
            amount = rate * line.quantity
            resolved.append(
                {
                    "item": item,
                    "rate": rate,
                    "quantity": line.quantity,
                    "amount": amount,
                    "batch_no": line.batch_no,
                    "expiry_date": line.expiry_date,
                }
            )
        return resolved
