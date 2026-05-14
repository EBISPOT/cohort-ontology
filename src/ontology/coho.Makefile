## Customize Makefile settings for coho
## 
## If you need to customize your Makefile, make
## changes here rather than in the main Makefile

# Override component template rules to add the COHO prefix mapping,
# which ROBOT needs to resolve COHO:XXXXXXX CURIEs in the CSV templates.
COHO_PREFIX = --prefix "COHO: http://www.ebi.ac.uk/coho/COHO_"

ifeq ($(COMP),true)

$(COMPONENTSDIR)/gaz_xrefs.owl: $(TEMPLATEDIR)/gaz_xrefs.tsv $(TMPDIR)/stamp-component-gaz_xrefs.owl
	$(ROBOT) template --prefix "dbpedia: http://dbpedia.org/resource/" --prefix "oio: http://www.geneontology.org/formats/oboInOwl#" \
		--template $(TEMPLATEDIR)/gaz_xrefs.tsv \
		$(ANNOTATE_CONVERT_FILE)
	# ROBOT template currently serializes BFO:0000050 restrictions as DataSomeValuesFrom.
	# Convert only those to ObjectSomeValuesFrom so object-property chains can reason over them.
	sed -i.bak 's/DataSomeValuesFrom(<http:\/\/purl.obolibrary.org\/obo\/BFO_0000050>/ObjectSomeValuesFrom(<http:\/\/purl.obolibrary.org\/obo\/BFO_0000050>/g' $(COMPONENTSDIR)/gaz_xrefs.owl && rm -f $(COMPONENTSDIR)/gaz_xrefs.owl.bak

$(COMPONENTSDIR)/GWAS.owl: $(TEMPLATEDIR)/GWAS.csv $(TMPDIR)/stamp-component-GWAS.owl
	$(ROBOT) template \
		$(COHO_PREFIX) \
		--template $(TEMPLATEDIR)/GWAS.csv \
		$(ANNOTATE_CONVERT_FILE)

$(COMPONENTSDIR)/MetaboLight.owl: $(TEMPLATEDIR)/MetaboLight.csv $(TMPDIR)/stamp-component-MetaboLight.owl
	$(ROBOT) template \
		$(COHO_PREFIX) \
		--template $(TEMPLATEDIR)/MetaboLight.csv \
		$(ANNOTATE_CONVERT_FILE)

$(COMPONENTSDIR)/EGA.owl: $(TEMPLATEDIR)/EGA.csv $(TMPDIR)/stamp-component-EGA.owl
	$(ROBOT) template \
		$(COHO_PREFIX) \
		--template $(TEMPLATEDIR)/EGA.csv \
		$(ANNOTATE_CONVERT_FILE)

$(COMPONENTSDIR)/PRIDE.owl: $(TEMPLATEDIR)/PRIDE.csv $(TMPDIR)/stamp-component-PRIDE.owl
	$(ROBOT) template \
		$(COHO_PREFIX) \
		--template $(TEMPLATEDIR)/PRIDE.csv \
		$(ANNOTATE_CONVERT_FILE)

endif # COMP=true
