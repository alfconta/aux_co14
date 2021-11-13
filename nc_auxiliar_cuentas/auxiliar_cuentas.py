# -*- coding: utf-8 -*-

from odoo import models, fields, api, SUPERUSER_ID, _
import odoo.addons.decimal_precision as dp
from odoo import tools
from odoo.tools.safe_eval import safe_eval
from odoo.tools import pycompat
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import float_is_zero
from datetime import datetime, date, time, timedelta
import calendar
import datetime
from dateutil.relativedelta import relativedelta
import xlsxwriter

from io import BytesIO
from pytz import timezone
import pytz
from odoo.exceptions import UserError

##############################################################################


from odoo.tools.misc import xlwt
import io
import base64
from xlwt import easyxf


class auxiliar_cuentas(models.TransientModel):
    _name = 'auxiliar.cuentas'
    _description = " Account movement report"

    @api.model
    def get_default_date_model(self):
        return pytz.UTC.localize(datetime.now()).astimezone(timezone(self.env.user.tz or 'UTC'))

    @api.model
    def _get_from_date(self):
        company = self.env.user.company_id
        current_date = datetime.date.today()
        from_date = company.compute_fiscalyear_dates(current_date)['date_from']
        return from_date

    excel_binary = fields.Binary('Field')
    file_name = fields.Char('Report_Name', readonly=True)
    
    company = fields.Many2one('res.company', required=True, default=lambda self: self.env.user.company_id,
                              string='Current Company')

   

    date_from = fields.Date(string='Date from', default=fields.Date.today)
    date_to = fields.Date(string='Date to', default=fields.Date.today)
    seleccion = fields.Selection([('grupos', 'Group'), ('cuenta', 'Account')], required=True, default='cuenta',
                              string='Selection search')

    grupo_cuenta=fields.Many2many('account.group',string='Grupos',help="Add Group account")
    cuenta =  fields.Many2one('account.account', string='Accounting account')

    revisio = fields.Char(string='revision')
    saldo_inicial = fields.Float(string='Ini.Balan')
    debe = fields.Float(string='Debit')
    haber = fields.Float(string='Credit')
    saldo_final = fields.Float(string='Fin.Balance')

  
    obj_auxiliar_cuentas_detalle= fields.One2many(comodel_name='auxiliar.cuentas.detalle', inverse_name='obj_auxiliar_cuentas')
    
 

            #return {'domain': {'ubicacion': [('company_id', '=', self.company.id), ('usage', '=', "internal")]}}

           
    def buscar_cuenta(self):
        if self.date_from > self.date_to:
            raise UserError(_("The Start date cannot be less than the end date "))
        else:
          if self.seleccion == 'grupos':
            self._action_imprimir_excel_grupos()                                
               
          else:   
            if  self.cuenta:   
              self._borrar()
            else:
              raise UserError(_("there must be at least 1 account"))     

    
    def _borrar(self):
       
        for tod in self:
          for tod1 in tod.obj_auxiliar_cuentas_detalle:  
           tod1.unlink()

        self._saldo_anterior_tabla()



    def _saldo_inicial(self):
        query_movimiento = """
        select (sum (debit) - sum (credit)) as saldo from 
(
select aml.id,rp.id as usuario,rp.name ,
aml.account_id,aml.write_uid,aml.move_id,aml.move_name,aml.date ,aml.create_date AT TIME ZONE 'UTC' as date_cr
,aml.company_id,aml.debit,aml.credit,sum(aml.debit-aml.credit) over (order by aml.date asc,aml.id asc) as balance from account_move_line aml
  inner join res_users  ru  on   aml.write_uid = ru.id 
  inner join res_partner  rp  on   rp.id = ru.partner_id
     where aml.account_id =%s  and aml.parent_state='posted' 
 group by rp.id,aml.id,aml.account_id,aml.move_id,aml.move_name,aml.date,aml.company_id,aml.debit,aml.credit )
  as sant  where date < %s 

        """
        return query_movimiento

    def _saldo_anterior_tabla(self):

        query_saldo_anterior =  self._saldo_inicial() 
        cuenta_num=self.cuenta.id
        fecha_ini=self.date_from
        query_saldo_anterior_param=(cuenta_num,fecha_ini)

        self.env.cr.execute(query_saldo_anterior, query_saldo_anterior_param)
        saldo_anterior = self.env.cr.dictfetchall()

        for auxiliar in self:
          for saldo in saldo_anterior:       
          
            self.saldo_inicial=saldo['saldo']
            concepto = "Previous balance"          
            line = ({'concepto': concepto, 'saldo': saldo['saldo'], })
            lines = [(0, 0, line)]
            auxiliar.write({'obj_auxiliar_cuentas_detalle': lines})
        self._movimiento_tabla()



    def _movimiento_tabla(self):  
        query_movimiento = """   
       ---- movimiento
select id,usuario,name,ref,account_id,write_uid,move_id,move_name,date,date_cr,
company_id,debit,credit,balance
from
(
select aml.id,rp.id as usuario,aml.ref,rp.name ,
aml.account_id,aml.write_uid,aml.move_id,aml.move_name,aml.date ,aml.create_date AT TIME ZONE 'UTC' 
as date_cr
,aml.company_id,aml.debit,aml.credit,sum(aml.debit-aml.credit) over (order by aml.date asc,aml.id asc)
 as balance from account_move_line aml
  inner join res_users  ru  on   aml.write_uid = ru.id 
  inner join res_partner  rp  on   rp.id = ru.partner_id
     where aml.account_id =%s  and aml.parent_state='posted' 
 group by rp.id,aml.id,aml.account_id,aml.move_id,aml.move_name,aml.date,aml.company_id,aml.debit,
 aml.credit  
 )
 as mov
 where date >=%s  and  date  <=%s order by  date asc

        """ 
          
        cuenta_num=self.cuenta.id
        fecha_ini=self.date_from
        fecha_fin=self.date_to
        query_movimiento_param=(cuenta_num,fecha_ini,fecha_fin,)   

        self.env.cr.execute(query_movimiento, query_movimiento_param)
        movimiento_axiliar= self.env.cr.dictfetchall()

        for auxiliar in self:
          for movimiento in movimiento_axiliar: 
            date= movimiento['date'] 
            date_cr= movimiento['date_cr']
            company_id= movimiento['company_id']
            usuario=movimiento['usuario'] 
            account_invoice=movimiento['move_id'] 
            concepto=movimiento['ref'] 
            debe=movimiento['debit'] 
            haber=movimiento['credit'] 
            saldo=movimiento['balance'] 
            line = ({'date': date,'date_cr': date_cr,'company_id':company_id,'usuario': usuario,
             'account_invoice': account_invoice,'concepto': concepto,
            'debe': debe, 
            'haber':haber, 'saldo': saldo, })
            lines = [(0, 0, line)]
            auxiliar.write({'obj_auxiliar_cuentas_detalle': lines})
        self._sumas_deb_cr()    

    def _sumas_deb_cr(self): 
        query_movimiento = """   
       ---- movimiento
select sum(debit) as debit, sum(credit) as credit ,(sum(debit)-sum(credit))as saldo
from
(
select aml.id,rp.id as usuario,aml.ref,rp.name ,
aml.account_id,aml.write_uid,aml.move_id,aml.move_name,aml.date ,aml.create_date AT TIME ZONE 'UTC' as date_cr
,aml.company_id,aml.debit,aml.credit,sum(aml.debit-aml.credit) over (order by aml.date asc,aml.id asc) as balance from account_move_line aml
  inner join res_users  ru  on   aml.write_uid = ru.id 
  inner join res_partner  rp  on   rp.id = ru.partner_id
     where aml.account_id =%s and aml.parent_state='posted' and aml.date >=%s and  
     aml.date  <=%s
 group by rp.id,aml.id,aml.account_id,aml.move_id,aml.move_name,aml.date,aml.company_id,aml.debit,aml.credit  
order by  aml.date asc
 
 )
 as mov
 


        """ 
          
        cuenta_num=self.cuenta.id
        fecha_ini=self.date_from
        fecha_fin=self.date_to
        query_movimiento_param=(cuenta_num,fecha_ini,fecha_fin,)   

        self.env.cr.execute(query_movimiento, query_movimiento_param)
        suma_axiliar= self.env.cr.dictfetchall()
        for movimiento in suma_axiliar: 
            self.debe=movimiento['debit'] 
            self.haber=movimiento['credit'] 
        self.saldo_final=self.saldo_inicial+ self.debe- self.haber  
        self._action_imprimir_excel()


    def _action_imprimir_excel(self ):

        workbook = xlwt.Workbook()
        column_heading_style = easyxf('font:height 200;font:bold True;')
        worksheet = workbook.add_sheet('Account movement report')
        date_format = xlwt.XFStyle()
        date_format.num_format_str = 'dd/mm/yyyy'

        number_format = xlwt.XFStyle()
        number_format.num_format_str = '#,##0.00'

        # Ponemos los primeros encabezados
        worksheet.write(0, 0, _('Account movement report'), column_heading_style)

        query_rorte = """
        select Max(id) as id  from auxiliar_cuentas
    """
        self.env.cr.execute(query_rorte, )
        tr = self.env.cr.dictfetchall()
        for tr_t in tr:
            todo_reporte = self.env['auxiliar.cuentas'].search([('id', '=', int(tr_t['id']))])
            tf = 0
            for todfact in todo_reporte:
                worksheet.write(1, 0, "Date from:", column_heading_style)
                worksheet.write(1, 1, todfact.date_from, date_format)
                worksheet.write(2, 0, "Date to:", column_heading_style)
                worksheet.write(2, 1, todfact.date_to, date_format)

                worksheet.write(1, 2, "Account:", column_heading_style)
                worksheet.write(1, 3, todfact.cuenta.name)
                worksheet.write(1, 4, "Code:", column_heading_style)
                worksheet.write(1, 5, todfact.cuenta.code)
                worksheet.write(2, 2, "Current Company:", column_heading_style)
                worksheet.write(2, 3, todfact.company.name)
                
                

                # Ponemos los primeros encabezados del detalle
        worksheet.write(4, 0, _('Date'), column_heading_style)
        worksheet.write(4, 1, _('Date_Cr'), column_heading_style)
        worksheet.write(4, 2, _('User'), column_heading_style)
        worksheet.write(4, 3, _('Journal'), column_heading_style)
        worksheet.write(4, 4, _('Description'), column_heading_style)
        worksheet.write(4, 5, _("Debit"), column_heading_style)
        worksheet.write(4, 6, _('Credit'), column_heading_style)
        worksheet.write(4, 7, _('Balance'), column_heading_style)
       
        heading = "Report"
        # worksheet.write_merge(5, 0, 5,13, heading, easyxf('font:height 200; align: horiz center;pattern: pattern solid, fore_color black; font: color white; font:bold True;' "borders: top thin,bottom thin"))
        # Se tiene que hacer de ultimo para saber cuanto mide todo

        # se recorre el reporte

        todo_reporte = self.env['auxiliar.cuentas.detalle'].search(
            [('obj_auxiliar_cuentas', '=', int(tr_t['id']))])
        tf = 0
        for todfact in todo_reporte:
            tf += 1
            ini = 5
            if  todfact.date != False :
              worksheet.write(tf + ini, 0, todfact.date, date_format)
            if  todfact.date_cr != False :  
              worksheet.write(tf + ini, 1, todfact.date_cr)
            if   todfact.usuario.name != False :   
             worksheet.write(tf + ini, 2, todfact.usuario.name)
            if   todfact.account_invoice.name != False :  
             worksheet.write(tf + ini, 3, todfact.account_invoice.name)
            if   todfact.concepto != False :  
             worksheet.write(tf + ini, 4, todfact.concepto)
            worksheet.write(tf + ini, 5, todfact.debe, number_format)
            worksheet.write(tf + ini, 6, todfact.haber, number_format)
            worksheet.write(tf + ini, 7, todfact.saldo, number_format)
           

        fp = io.BytesIO()
        workbook.save(fp)
        excel_file = base64.encodestring(fp.getvalue())

        self.excel_binary = excel_file
        nombre_tabla = "Account Report.xls"
        self.file_name = nombre_tabla
        fp.close()

    


    def _action_imprimir_excel_prueba(self ):
                
    
                query_contamos = """
                    select count (id) cantidad from 
    (select id,usuario,name,ref,account_id,write_uid,move_id,move_name,date,date_cr,company_id,debit,credit,balance
    from
    (
    select aml.id,rp.id as usuario,aml.ref,rp.name ,
    aml.account_id,aml.write_uid,aml.move_id,aml.move_name,aml.date ,aml.create_date AT TIME ZONE 'UTC' as date_cr
    ,aml.company_id,aml.debit,aml.credit,sum(aml.debit-aml.credit) over (order by aml.date asc,aml.id asc) as balance from account_move_line aml
    inner join res_users  ru  on   aml.write_uid = ru.id 
    inner join res_partner  rp  on   rp.id = ru.partner_id
        where aml.account_id =%s  and aml.parent_state='posted' 
    group by rp.id,aml.id,aml.account_id,aml.move_id,aml.move_name,aml.date,aml.company_id,aml.debit,aml.credit  
    )
    as mov
    where date >=%s  and  date  <=%s  order by  date asc  )as todo

                    """
                                    
                cuenta=2
                
                fecha_ini=self.date_from
                fecha_fin=self.date_to
                query_contamos_param = (cuenta,fecha_ini,fecha_fin,)
                self.env.cr.execute(query_contamos,query_contamos_param, )
                total_ctas = self.env.cr.dictfetchall()                   
                for t_ctas in total_ctas:                                         
                    query_insertartotal = """
                        INSERT INTO auxiliar_cuentas_conteo (detalle_conteo) VALUES (%s);

                        """
                                        
                    num_fiilas=t_ctas ['cantidad'] + 20
                        
                    query_insertartotal_param = (num_fiilas,)
                    self.env.cr.execute(query_insertartotal,query_insertartotal_param , )
                #raise UserError(num_fiilas) 
                  
    t_row_cta = 0
    def _action_imprimir_excel_grupos(self ):



            workbook = xlwt.Workbook()
            worksheet = workbook.add_sheet('Account movement report')
            column_heading_style = easyxf('font:height 200;font:bold True;')  
            worksheet.write(0, 0, _('Account movement reports'), column_heading_style)
            
            date_format = xlwt.XFStyle()
            date_format.num_format_str = 'dd/mm/yyyy'
            number_format = xlwt.XFStyle()
            number_format.num_format_str = '#,##0.00'
            num=0 
            num_fiilas=0
            t_row_cta=0


            grupos = self.grupo_cuenta  
            for g in grupos:        
             # repasamos grupo por grupo   
                id_gr=g.id
                query_cuenta = """
                    select * from account_account  where group_id = %s order by id asc
                    """ 
                query_cuenta_param =(id_gr,)
                self.env.cr.execute(query_cuenta,query_cuenta_param )
                cuentas_agrupada = self.env.cr.dictfetchall()       
                for cta in cuentas_agrupada :
                #Comenzamos a repasar cuenta por cuenta
                    num += 1


                    #contamos las filas    
                    num_cta=0
                    if  num == 1:
                        num_cta=0 
            
                    if  num > 1:                           
                        query_conteo_anterior = """
                                ---- conteo anterior
                        select detalle_conteo from auxiliar_cuentas_conteo

                            """                                       
                    
                        self.env.cr.execute( query_conteo_anterior)
                        conteo_anterior = self.env.cr.dictfetchall()  
                        for conteo in conteo_anterior:
                            num_cta=conteo['detalle_conteo']   
                            #raise UserError(num_cta)  
                
               

                    worksheet.write(1 + num_cta , 0, "Date from:", column_heading_style)
                    worksheet.write(1 + num_cta, 1, self.date_from, date_format)
                    worksheet.write(2+ num_cta , 0, "Date to:", column_heading_style)
                    worksheet.write(2 + num_cta, 1, self.date_to, date_format)
                    worksheet.write(1 + num_cta, 2, "Account:", column_heading_style)
                    worksheet.write(1 + num_cta, 3, cta['code'])
                    worksheet.write(1 + num_cta, 4, cta['name'])            
                    worksheet.write(2+ num_cta, 2, "Current Company:", column_heading_style)
                    worksheet.write(2+ num_cta, 3, self.company.name)
                    worksheet.write(2+ num_cta, 4, "Selection Group:", column_heading_style)
                    worksheet.write(2+ num_cta, 5, g['name'])
                                                
                                            # Ponemos los primeros encabezados del detalle
                    worksheet.write(4 + num_cta, 0, _('Date'), column_heading_style)
                    worksheet.write(4 + num_cta, 1, _('Date_Cr'), column_heading_style)
                    worksheet.write(4 + num_cta, 2, _('User'), column_heading_style)
                    worksheet.write(4 + num_cta, 3, _('Journal'), column_heading_style)
                    worksheet.write(4 + num_cta, 4, _('Description'), column_heading_style)
                    worksheet.write(4 + num_cta, 5, _("Debit"), column_heading_style)
                    worksheet.write(4 + num_cta, 6, _('Credit'), column_heading_style)
                    worksheet.write(4 + num_cta, 7, _('Balance'), column_heading_style)
                
                        #heading = "Report"
                        # worksheet.write_merge(5, 0, 5,13, heading, easyxf('font:height 200; align: horiz center;pattern: pattern solid, fore_color black; font: color white; font:bold True;' "borders: top thin,bottom thin"))
                        # Se tiene que hacer de ultimo para saber cuanto mide todo

                        # se recorre el reporte
        
        
        
                        #Ponemos el saldo anterior
                    query_report = """
                                ---- saldo anterior
                        select (sum (debit) - sum (credit)) as saldo from 
                        (
                        select aml.id,rp.id as usuario,rp.name ,
                        aml.account_id,aml.write_uid,aml.move_id,aml.move_name,aml.date ,aml.create_date AT TIME ZONE 'UTC' as date_cr
                        ,aml.company_id,aml.debit,aml.credit,sum(aml.debit-aml.credit) over (order by aml.date asc,aml.id asc) as balance from account_move_line aml
                        inner join res_users  ru  on   aml.write_uid = ru.id 
                        inner join res_partner  rp  on   rp.id = ru.partner_id
                            where aml.account_id = %s and aml.parent_state='posted' 
                        group by rp.id,aml.id,aml.account_id,aml.move_id,aml.move_name,aml.date,aml.company_id,aml.debit,aml.credit )
                        as sant  where date < %s

                            """ 
                    cuenta=cta['id']
                    de=self.date_from           
                    query_report_param =(cuenta,de,)
                    self.env.cr.execute(query_report, query_report_param)
                    tr = self.env.cr.dictfetchall()  
                            
                    for sal_ini in tr :
                        #Repasamos linea por linea
                        worksheet.write(5+ num_cta, 4, "Previous balance" , date_format)
                        worksheet.write(5+ num_cta, 7, sal_ini['saldo'] , number_format) 
                        
                    
                    ini = 5
                    tf =0
                    query_movimiento = """   
                        ---- movimiento
                        select id,usuario,name,ref,account_id,write_uid,move_id,move_name,date,date_cr,
                            company_id,debit,credit,balance
                        from
                        (
                        select aml.id,rp.id as usuario,aml.ref,rp.name ,
                        aml.account_id,aml.write_uid,aml.move_id,aml.move_name,aml.date ,aml.create_date AT TIME ZONE 'UTC' 
                        as date_cr
                        ,aml.company_id,aml.debit,aml.credit,sum(aml.debit-aml.credit) over (order by aml.date asc,aml.id asc)
                        as balance from account_move_line aml
                        inner join res_users  ru  on   aml.write_uid = ru.id 
                        inner join res_partner  rp  on   rp.id = ru.partner_id
                            where aml.account_id =%s  and aml.parent_state='posted' 
                        group by rp.id,aml.id,aml.account_id,aml.move_id,aml.move_name,aml.date,aml.company_id,aml.debit,
                        aml.credit  
                        )
                        as mov
                        where date >=%s  and  date  <=%s order by  date asc

                                """ 
                                
                    cuenta_num=cta['id']
                    fecha_ini=self.date_from
                    fecha_fin=self.date_to
                    query_movimiento_param=(cuenta_num,fecha_ini,fecha_fin,) 
                    self.env.cr.execute(query_movimiento, query_movimiento_param)
                    movimiento_axiliar= self.env.cr.dictfetchall()                
                    for todfact in movimiento_axiliar:
                        #Repasamos las filas de cada cuenta 
                            tf += 1
                        
                            
                            worksheet.write(tf + ini + num_cta, 0, todfact['date'], date_format)                     
                            if  todfact['date_cr'] != False :  
                             worksheet.write(tf + ini + num_cta, 1,str( todfact['date_cr']))
                            if    todfact['name'] != False :   
                                worksheet.write(tf + ini + num_cta, 2,  todfact['name'])
                            if   todfact['move_name']   != False :  
                                worksheet.write(tf + ini + num_cta, 3,todfact['move_name'] )
                            if   todfact['ref']  != False :  
                                worksheet.write(tf + ini + num_cta, 4,  todfact['ref'] )
                            worksheet.write(tf + ini + num_cta, 5,todfact['debit'], number_format)
                            worksheet.write(tf + ini + num_cta, 6, todfact['credit'], number_format)
                            worksheet.write(tf + ini+ num_cta , 7, todfact['balance'], number_format)
                    worksheet.write(1 +tf + ini+ num_cta , 4, "==================================>>  END  Account: "+cta['code']+" "+ cta['name']+ "<<======================================" , date_format)
                        #contamos las filas    
                    
                        
                    #ctotal_filas_cuenta=self.env['account.account'].search_count([('id','=',cta['id']),('date','>=',fecha_ini), '|',('date','<=',fecha_fin)])
                    
    
                    query_contamos = """
                        select count (id) cantidad from 
                (select id,usuario,name,ref,account_id,write_uid,move_id,move_name,date,date_cr,company_id,debit,credit,balance
                from
                (
                select aml.id,rp.id as usuario,aml.ref,rp.name ,
                aml.account_id,aml.write_uid,aml.move_id,aml.move_name,aml.date ,aml.create_date AT TIME ZONE 'UTC' as date_cr
                ,aml.company_id,aml.debit,aml.credit,sum(aml.debit-aml.credit) over (order by aml.date asc,aml.id asc) as balance from account_move_line aml
                inner join res_users  ru  on   aml.write_uid = ru.id 
                inner join res_partner  rp  on   rp.id = ru.partner_id
                    where aml.account_id =%s  and aml.parent_state='posted' 
                group by rp.id,aml.id,aml.account_id,aml.move_id,aml.move_name,aml.date,aml.company_id,aml.debit,aml.credit  
                )
                as mov
                where date >=%s  and  date  <=%s  order by  date asc  )as todo

                                """
                                        
                    cuenta=cta['id']
                    
                    fecha_ini=self.date_from
                    fecha_fin=self.date_to
                    query_contamos_param = (cuenta,fecha_ini,fecha_fin,)
                    self.env.cr.execute(query_contamos,query_contamos_param, )
                    total_ctas = self.env.cr.dictfetchall()                   
                    for t_ctas in total_ctas:    



                        query_insertartotal = """
                            INSERT INTO auxiliar_cuentas_conteo (detalle_conteo) VALUES (%s);

                            """
                        num_fiilas=0
                        if  num == 1:
                         num_fiilas=t_ctas ['cantidad'] +  9

                        if  num > 1:                           
                            query_conteo_anterior2 = """
                                    ---- conteo anterior
                            select detalle_conteo from auxiliar_cuentas_conteo

                                """                                       
                        
                            self.env.cr.execute( query_conteo_anterior2)
                            conteo_anterior2 = self.env.cr.dictfetchall()  
                            for conteo2 in conteo_anterior2:
                                num_cta2=conteo2['detalle_conteo']                       
                                num_fiilas=t_ctas ['cantidad'] + num_cta2 + 9
                                # debedebes de sumar los espacios cuando no haya movimientos
                                query_conteo_eliminar = """
                                    ---- conteo anterior
                                delete  from  auxiliar_cuentas_conteo

                                """    
                                self.env.cr.execute( query_conteo_eliminar)




                        query_insertartotal_param = (num_fiilas,)
                        self.env.cr.execute(query_insertartotal,query_insertartotal_param , )
               

            fp = io.BytesIO()
            workbook.save(fp)
            excel_file = base64.encodestring(fp.getvalue())
            self.excel_binary = excel_file
            nombre_tabla = "Account Report.xls"
            self.file_name = nombre_tabla
            fp.close()
        

        


       
      


class auxiliar_cuentas_detalle(models.TransientModel):
    _name = 'auxiliar.cuentas.detalle'
    _description = "Account movement report detail"

    obj_auxiliar_cuentas = fields.Many2one('auxiliar.cuentas')

    date = fields.Date(string='Date')
    date_cr = fields.Char(string='Date cr')
    company_id = fields.Many2one('res.company', string='Company')
    usuario=fields.Many2one('res.partner', string='User')
    
    account_invoice = fields.Many2one('account.move', string='Journal')    
    
    concepto = fields.Char(string='Description')  
    
    
    debe = fields.Float(string='Debit')
    haber = fields.Float(string='Credit')
    saldo= fields.Float(string='Balance')


class auxiliar_cuentas_conteo(models.TransientModel):
    _name = 'auxiliar.cuentas.conteo'
    _description = "Account movement report conteo"

    detalle_conteo = fields.Integer(string='d_conbteo')
    #debe = fields.Float(string='Debit')




    
